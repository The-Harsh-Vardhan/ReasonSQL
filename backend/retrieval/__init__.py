"""
Retrieval module for ReasonSQL 2.0.

Provides hybrid schema retrieval:
- FAISS vector index (semantic search)
- BM25 keyword retrieval
- Cross-Encoder reranking

Public API:
    from backend.retrieval import HybridSchemaRetriever, SchemaIndexer
"""

from .schema_indexer import SchemaIndexer
from .hybrid_retriever import HybridSchemaRetriever

__all__ = ["SchemaIndexer", "HybridSchemaRetriever"]
