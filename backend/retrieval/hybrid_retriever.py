"""
Hybrid Schema Retriever — BM25 + FAISS + Cross-Encoder Reranking.

Pipeline:
    1. BM25 keyword retrieval   → top-K candidates (lexical match)
    2. FAISS semantic retrieval → top-K candidates (semantic match)
    3. Reciprocal Rank Fusion   → merge both candidate lists
    4. Cross-Encoder reranking  → precision rerank via query-document scoring

Why Hybrid Retrieval?
    - BM25 excels at exact keyword matches (table names, column names in query)
    - FAISS excels at semantic understanding ("customers" → "Customer" table)
    - Fusion captures both strengths; Cross-Encoder eliminates false positives

Cross-Encoder vs Bi-Encoder:
    - Bi-encoder (FAISS): Query and document encoded separately → fast but less precise
    - Cross-encoder: Query + document encoded together → slow but highly precise
    - We use bi-encoder for candidate retrieval (speed) + cross-encoder for reranking (precision)
"""

import logging
from typing import List, Dict, Tuple, Optional

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document

from .schema_indexer import SchemaIndexer
from configs import RERANKER_MODEL, HYBRID_RETRIEVAL_K, RERANKER_TOP_N

logger = logging.getLogger("reasonsql.retrieval.hybrid")


class HybridSchemaRetriever:
    """
    Hybrid schema retriever combining BM25 + FAISS + Cross-Encoder reranking.

    Usage:
        indexer = SchemaIndexer()
        indexer.index_schema(table_schemas)

        retriever = HybridSchemaRetriever(indexer)
        relevant_tables = retriever.retrieve("top customers by revenue", k=5)
        # Returns: ["Customer", "Invoice", "InvoiceLine"]
    """

    def __init__(
        self,
        indexer: SchemaIndexer,
        reranker_model: str = RERANKER_MODEL,
    ):
        """
        Initialize the hybrid retriever.

        Args:
            indexer: A SchemaIndexer with an indexed FAISS vectorstore
            reranker_model: HuggingFace cross-encoder model name
        """
        self.indexer = indexer
        self._reranker_model_name = reranker_model
        self._reranker: Optional[CrossEncoder] = None  # Lazy load

        # Build BM25 index from the same documents as FAISS
        if indexer.documents:
            self._build_bm25(indexer.documents)
        else:
            self.bm25: Optional[BM25Okapi] = None
            self._bm25_docs: List[Document] = []
            logger.warning("HybridRetriever: No documents in indexer yet; BM25 not initialized.")

        logger.info(
            "HybridSchemaRetriever ready (BM25 + FAISS + CrossEncoder: %s)",
            reranker_model,
        )

    def _build_bm25(self, documents: List[Document]) -> None:
        """Build BM25 index from document list."""
        self._bm25_docs = documents
        tokenized = [doc.page_content.lower().split() for doc in documents]
        self.bm25 = BM25Okapi(tokenized)
        logger.debug("BM25 index built: %d documents", len(documents))

    @property
    def reranker(self) -> CrossEncoder:
        """Lazy-load the cross-encoder model."""
        if self._reranker is None:
            logger.info("Loading cross-encoder reranker: %s", self._reranker_model_name)
            self._reranker = CrossEncoder(self._reranker_model_name)
            logger.info("Cross-encoder reranker loaded.")
        return self._reranker

    def retrieve(
        self,
        query: str,
        k: int = HYBRID_RETRIEVAL_K,
        rerank_top_n: int = RERANKER_TOP_N,
    ) -> List[str]:
        """
        Retrieve the most relevant table names for a query.

        Pipeline:
            BM25(k) + FAISS(k) → RRF fusion → CrossEncoder rerank → top-N tables

        Args:
            query: Natural language query
            k: Number of candidates from each retriever (BM25 + FAISS)
            rerank_top_n: Final number of tables to return after reranking

        Returns:
            List of table names, most relevant first
        """
        if self.bm25 is None or self.indexer.vectorstore is None:
            logger.error("Retriever not initialized. Index schema first.")
            return []

        # --- Step 1: BM25 keyword retrieval ---
        bm25_results = self._bm25_retrieve(query, k=k)

        # --- Step 2: FAISS semantic retrieval ---
        faiss_results = self._faiss_retrieve(query, k=k)

        # --- Step 3: Reciprocal Rank Fusion ---
        fused_docs = self._reciprocal_rank_fusion(bm25_results, faiss_results)

        if not fused_docs:
            logger.warning("Hybrid retrieval returned no candidates for: %r", query)
            return []

        # Cap candidates to avoid slow cross-encoder on many docs
        candidates = fused_docs[:max(rerank_top_n * 2, 10)]

        # --- Step 4: Cross-Encoder reranking ---
        reranked_docs = self._cross_encoder_rerank(query, candidates, top_n=rerank_top_n)

        table_names = [doc.metadata["table"] for doc in reranked_docs]
        logger.info(
            "Hybrid retrieval for %r: BM25(%d) + FAISS(%d) → RRF(%d) → reranked → %s",
            query, len(bm25_results), len(faiss_results), len(candidates), table_names,
        )
        return table_names

    def _bm25_retrieve(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """BM25 keyword retrieval."""
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)

        # Sort by score descending, return top-k
        ranked = sorted(
            zip(self._bm25_docs, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(doc, score) for doc, score in ranked[:k] if score > 0]

    def _faiss_retrieve(self, query: str, k: int) -> List[Tuple[Document, float]]:
        """FAISS semantic retrieval."""
        try:
            return self.indexer.semantic_search(query, k=k)
        except Exception as e:
            logger.error("FAISS retrieval failed: %s", e)
            return []

    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[Tuple[Document, float]],
        faiss_results: List[Tuple[Document, float]],
        rrf_k: int = 60,
    ) -> List[Document]:
        """
        Reciprocal Rank Fusion (RRF) to merge two ranked lists.

        RRF score = Σ 1/(k + rank_i) for each result list
        This is a parameter-free, robust fusion method.

        Args:
            bm25_results: (Document, score) from BM25
            faiss_results: (Document, score) from FAISS
            rrf_k: RRF constant (default 60, per the original paper)

        Returns:
            Merged, deduplicated list of Documents sorted by RRF score
        """
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}

        def _add_results(results: List[Tuple[Document, float]]) -> None:
            for rank, (doc, _score) in enumerate(results, start=1):
                table = doc.metadata["table"]
                doc_map[table] = doc
                rrf_scores[table] = rrf_scores.get(table, 0.0) + (1.0 / (rrf_k + rank))

        _add_results(bm25_results)
        _add_results(faiss_results)

        # Sort by RRF score descending
        sorted_tables = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_map[table] for table, _ in sorted_tables]

    def _cross_encoder_rerank(
        self,
        query: str,
        candidates: List[Document],
        top_n: int,
    ) -> List[Document]:
        """
        Rerank candidates using a cross-encoder for precision.

        The cross-encoder jointly encodes (query, document) pairs and scores
        their relevance — much more accurate than bi-encoder similarity.

        Args:
            query: Natural language query
            candidates: Candidate documents from RRF fusion
            top_n: Number of documents to return

        Returns:
            Top-N reranked documents
        """
        if not candidates:
            return []

        # Build (query, document) pairs for cross-encoder
        pairs = [(query, doc.page_content) for doc in candidates]

        try:
            scores = self.reranker.predict(pairs)
        except Exception as e:
            logger.error("Cross-encoder reranking failed: %s. Returning unfused results.", e)
            return candidates[:top_n]

        # Sort by cross-encoder score descending
        scored = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

        reranked = [doc for doc, _ in scored[:top_n]]
        logger.debug(
            "Cross-encoder reranked %d → top-%d: %s",
            len(candidates),
            top_n,
            [doc.metadata["table"] for doc in reranked],
        )
        return reranked
