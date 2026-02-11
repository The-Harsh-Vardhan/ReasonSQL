"""Test database adapter imports and basic functionality."""
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.adapters import SQLiteAdapter, create_adapter, DatabaseType

DB_PATH = "./data/chinook.db"
db_exists = os.path.exists(DB_PATH)


def test_adapter_imports():
    """Verify adapter classes can be imported."""
    assert SQLiteAdapter is not None
    assert create_adapter is not None
    assert DatabaseType is not None


@pytest.mark.skipif(not db_exists, reason="chinook.db not available in CI")
def test_create_sqlite_adapter():
    """Test creating an adapter and reading schema (requires local DB)."""
    adapter = create_adapter(DatabaseType.SQLITE, file_path=DB_PATH)
    schema = adapter.get_schema()
    assert len(schema["tables"]) > 0
    table_names = [t["name"] for t in schema["tables"]]
    assert len(table_names) >= 3
