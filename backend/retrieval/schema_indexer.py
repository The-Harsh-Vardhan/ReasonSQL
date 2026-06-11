"""
Schema Indexer — FAISS Vector Store for Database Schemas.

Builds a FAISS index of database table schemas using HuggingFace embeddings.
This enables semantic similarity search to find relevant tables for a query.

Architecture:
    table schemas (text) → HuggingFaceEmbeddings → FAISS index → similarity_search()

Why FAISS over hand-rolled cosine:
- Optimized ANN (Approximate Nearest Neighbor) algorithms (IVF, HNSW)
- Persists to disk — no re-embedding on restart
- Integrates natively with LangChain retriever interface
- Supports metadata filtering (by table name, schema, etc.)
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

from configs import EMBEDDING_MODEL

logger = logging.getLogger("reasonsql.retrieval.indexer")


class SchemaIndexer:
    """
    Indexes database table schemas into a FAISS vector store.

    Each table is represented as a LangChain Document:
        page_content: human-readable schema string
        metadata: {"table": table_name}

    This enables:
    - Semantic similarity search (find tables relevant to a query)
    - Metadata-based filtering (filter by table name)
    - Integration with LangChain retrievers
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        """
        Initialize the schema indexer.

        Args:
            model_name: HuggingFace sentence-transformers model name.
                        Default: 'all-MiniLM-L6-v2' (fast, 384-dim, 80MB)
        """
        self._model_name = model_name
        self._embeddings: Optional[HuggingFaceEmbeddings] = None  # Lazy load
        self.vectorstore: Optional[FAISS] = None
        self.documents: List[Document] = []

        logger.info("SchemaIndexer initialized (model: %s, lazy-loaded)", model_name)

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Lazy-load the embedding model to avoid loading PyTorch at import time."""
        if self._embeddings is None:
            logger.info("Loading embedding model: %s", self._model_name)
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self._model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},  # Cosine similarity
            )
            logger.info("Embedding model loaded.")
        return self._embeddings

    def index_schema(self, table_schemas: Dict[str, str]) -> FAISS:
        """
        Build a FAISS index from table schema strings.

        Args:
            table_schemas: Dict mapping table_name → schema text string.
                           e.g. {"Artist": 'Table "Artist": "ArtistId" INTEGER PK | "Name" TEXT'}

        Returns:
            FAISS vectorstore instance
        """
        if not table_schemas:
            raise ValueError("Cannot index empty schema — no tables provided.")

        logger.info("Indexing %d tables into FAISS...", len(table_schemas))

        # Create LangChain Documents (one per table)
        self.documents = [
            Document(
                page_content=schema_text,
                metadata={"table": table_name},
            )
            for table_name, schema_text in table_schemas.items()
        ]

        # Build FAISS index
        self.vectorstore = FAISS.from_documents(self.documents, self.embeddings)

        logger.info("FAISS index built: %d vectors, dim=%d", len(self.documents), self._get_dimension())
        return self.vectorstore

    def semantic_search(self, query: str, k: int = 10) -> List[tuple[Document, float]]:
        """
        Perform semantic similarity search in the FAISS index.

        Args:
            query: Natural language query
            k: Number of results to return

        Returns:
            List of (Document, similarity_score) tuples, sorted by score desc
        """
        if self.vectorstore is None:
            raise RuntimeError("Schema not indexed yet. Call index_schema() first.")

        results = self.vectorstore.similarity_search_with_score(query, k=k)
        # FAISS returns L2 distance (lower = more similar); convert to similarity
        return [(doc, 1.0 / (1.0 + score)) for doc, score in results]

    def save(self, path: str | Path) -> None:
        """
        Persist FAISS index to disk.

        Args:
            path: Directory path to save index files
        """
        if self.vectorstore is None:
            raise RuntimeError("No index to save. Call index_schema() first.")
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.vectorstore.save_local(str(path))
        logger.info("FAISS index saved to %s", path)

    def load(self, path: str | Path) -> None:
        """
        Load a previously saved FAISS index from disk.

        Args:
            path: Directory path containing saved index files
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"FAISS index not found at: {path}")
        self.vectorstore = FAISS.load_local(
            str(path),
            self.embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info("FAISS index loaded from %s", path)

    def _get_dimension(self) -> int:
        """Get embedding dimension from the index."""
        try:
            return self.vectorstore.index.d
        except Exception:
            return -1
