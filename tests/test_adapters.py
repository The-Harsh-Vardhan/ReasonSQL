"""Test database adapter imports."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.adapters import SQLiteAdapter, create_adapter, DatabaseType

print("Adapter imports OK")
adapter = create_adapter(DatabaseType.SQLITE, file_path="./data/chinook.db")
schema = adapter.get_schema()
print(f"Schema: {len(schema['tables'])} tables")
print("Sample tables:", [t['name'] for t in schema['tables'][:3]])
