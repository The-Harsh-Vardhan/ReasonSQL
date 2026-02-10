#!/usr/bin/env python3
"""
Minimal database download script for CI/CD deployments.
Downloads the Chinook database if it doesn't exist.
"""
import os
import urllib.request
from pathlib import Path


def download_database():
    """Download Chinook SQLite database."""
    data_dir = Path("data")
    db_path = data_dir / "chinook.db"
    
    # Create data directory if needed
    data_dir.mkdir(exist_ok=True)
    
    if db_path.exists():
        print(f"[OK] Database already exists at {db_path}")
        return True
    
    print(f"[INFO] Downloading Chinook database to {db_path}...")
    
    url = "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
    
    try:
        urllib.request.urlretrieve(url, db_path)
        print(f"[OK] Database downloaded successfully ({db_path.stat().st_size} bytes)")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download database: {e}")
        return False


if __name__ == "__main__":
    success = download_database()
    exit(0 if success else 1)
