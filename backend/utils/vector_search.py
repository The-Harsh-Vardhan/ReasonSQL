
try:
    import numpy as np
except ImportError:
    np = None  # Graceful fallback when numpy not installed
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Lazy-load sentence-transformers to avoid importing PyTorch at startup
# This saves ~400MB of memory on constrained environments like Render free tier
_model = None
_model_name = 'all-MiniLM-L6-v2'

def _get_model():
    """Lazy-load the SentenceTransformer model on first use."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {_model_name}")
            _model = SentenceTransformer(_model_name)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
    return _model


class SchemaVectorStore:
    """
    In-memory vector store for table schema embeddings.
    Uses 'all-MiniLM-L6-v2' for fast, lightweight local embeddings.
    Model is loaded lazily on first use (not at import time).
    """
    
    def __init__(self):
        self.table_embeddings: Dict[str, np.ndarray] = {}
        self.table_schemas: Dict[str, str] = {}
        
    @property
    def model(self):
        return _get_model()

    def add_table(self, table_name: str, schema_text: str):
        """
        Add a table schema to the vector store.
        schema_text should include table name, column names, and descriptions.
        """
        if not self.model:
            return

        try:
            embedding = self.model.encode(schema_text)
            self.table_embeddings[table_name] = embedding
            self.table_schemas[table_name] = schema_text
        except Exception as e:
            logger.error(f"Failed to embed table {table_name}: {e}")

    def search(self, query: str, k: int = 5) -> List[str]:
        """
        Find top-k relevant tables for a natural language query.
        Returns a list of table names.
        """
        if not self.model or not self.table_embeddings:
            return []

        try:
            query_embedding = self.model.encode(query)
            
            similarities = []
            for table_name, table_embedding in self.table_embeddings.items():
                score = self._cosine_similarity(query_embedding, table_embedding)
                similarities.append((table_name, score))
            
            # Sort by score descending
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            # Return top-k table names
            return [name for name, _ in similarities[:k]]
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return list(self.table_embeddings.keys())[:k]  # Fallback

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return np.dot(a, b) / (norm_a * norm_b)

# Global instance — model is NOT loaded here, only on first .search() or .add_table()
schema_vector_store = SchemaVectorStore()
