"""
API endpoint tests for ReasonSQL backend.

Uses FastAPI TestClient — no running server or LLM required.
Tests validate the API layer: routing, validation, error handling, and response shape.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment BEFORE any app imports
os.environ.setdefault("GOOGLE_API_KEY", "test-key-for-ci")
os.environ.setdefault("GEMINI_API_KEY", "test-key-for-ci")
os.environ.setdefault("LLM_PROVIDER", "gemini")
os.environ.setdefault("ENABLE_DEBUG_ENDPOINTS", "false")

from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


# =============================================================================
# HEALTH ENDPOINT
# =============================================================================

class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_shape(self):
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "database_connected" in data
        assert "tables" in data
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"


# =============================================================================
# QUERY ENDPOINT
# =============================================================================

class TestQueryEndpoint:
    """Tests for POST /query."""

    def test_query_unknown_database_returns_404(self):
        response = client.post("/query", json={
            "query": "How many customers?",
            "database_id": "nonexistent_db",
        })
        assert response.status_code == 404

    def test_query_empty_string_returns_422(self):
        response = client.post("/query", json={
            "query": "",
        })
        assert response.status_code == 422

    def test_query_missing_field_returns_422(self):
        response = client.post("/query", json={})
        assert response.status_code == 422

    def test_query_too_long_returns_422(self):
        long_query = "a" * 2001
        response = client.post("/query", json={
            "query": long_query,
        })
        assert response.status_code == 422


# =============================================================================
# DATABASES ENDPOINT
# =============================================================================

class TestDatabasesEndpoint:
    """Tests for /databases routes."""

    def test_list_databases_returns_200(self):
        response = client.get("/databases")
        assert response.status_code == 200
        data = response.json()
        assert "databases" in data
        assert isinstance(data["databases"], list)

    def test_register_sqlite_missing_path_returns_400(self):
        response = client.post("/databases", json={
            "id": "test_db",
            "type": "sqlite",
        })
        assert response.status_code == 400

    def test_register_postgres_missing_string_returns_400(self):
        response = client.post("/databases", json={
            "id": "test_db",
            "type": "postgres",
        })
        assert response.status_code == 400

    def test_get_schema_unknown_db_returns_404(self):
        response = client.get("/databases/nonexistent_db_xyz/schema")
        assert response.status_code == 404


# =============================================================================
# DEBUG ENDPOINT
# =============================================================================

class TestDebugEndpoint:
    """Tests for GET /debug-db."""

    def test_debug_disabled_returns_404(self):
        """When ENABLE_DEBUG_ENDPOINTS=false, debug-db should return 404."""
        response = client.get("/debug-db")
        assert response.status_code == 404
