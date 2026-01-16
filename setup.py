#!/usr/bin/env python3
"""
Setup script for NL2SQL Multi-Agent System.
Downloads the Chinook database and verifies configuration.
"""
import os
import sys
import urllib.request
import shutil
from pathlib import Path


def print_header():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           NL2SQL Multi-Agent System Setup                     ║
╚═══════════════════════════════════════════════════════════════╝
    """)


def check_python_version():
    """Check Python version is 3.10+"""
    print("Checking Python version...", end=" ")
    if sys.version_info < (3, 10):
        print("❌ FAILED")
        print(f"  Python 3.10+ required, found {sys.version}")
        return False
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True


def create_directories():
    """Create required directories."""
    print("Creating directories...", end=" ")
    dirs = ["data", "logs"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
    print("✓")


def download_chinook_database():
    """Download Chinook SQLite database."""
    data_dir = Path("data")
    db_path = data_dir / "chinook.db"
    
    if db_path.exists():
        print(f"Database already exists at {db_path}")
        return True
    
    print("Downloading Chinook database...", end=" ")
    
    # URL for the Chinook SQLite database
    url = "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
    
    try:
        urllib.request.urlretrieve(url, db_path)
        print("✓")
        return True
    except Exception as e:
        print("❌ FAILED")
        print(f"  Error downloading database: {e}")
        print("  Please download manually from:")
        print("  https://github.com/lerocha/chinook-database")
        print(f"  And place it at: {db_path.absolute()}")
        return False


def create_env_file():
    """Create .env file if it doesn't exist."""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print(f".env file already exists")
        return True
    
    if env_example.exists():
        print("Creating .env from .env.example...", end=" ")
        shutil.copy(env_example, env_file)
        print("✓")
    else:
        print("Creating .env file...", end=" ")
        env_content = """# NL2SQL Multi-Agent System Configuration

# LLM Configuration (Choose one provider)
# Option 1: Groq (recommended - fast and free tier available)
GROQ_API_KEY=your_groq_api_key_here
LLM_PROVIDER=groq
LLM_MODEL=groq/llama-3.1-70b-versatile

# Option 2: Google Gemini (alternative)
# GOOGLE_API_KEY=your_google_api_key_here
# LLM_PROVIDER=gemini
# LLM_MODEL=gemini/gemini-pro

# Database Configuration
DATABASE_PATH=./data/chinook.db

# System Settings
VERBOSE=true
MAX_RETRIES=3
DEFAULT_LIMIT=100
"""
        env_file.write_text(env_content)
        print("✓")
    
    print("\n⚠️  IMPORTANT: Edit .env and add your API key!")
    return True


def check_api_key():
    """Check if API key is configured."""
    from dotenv import load_dotenv
    load_dotenv()
    
    groq_key = os.getenv("GROQ_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY")
    
    if groq_key and groq_key != "your_groq_api_key_here":
        print("✓ Groq API key configured")
        return True
    elif google_key and google_key != "your_google_api_key_here":
        print("✓ Google API key configured")
        return True
    else:
        print("⚠️  No API key configured")
        print("  Please edit .env and add your GROQ_API_KEY or GOOGLE_API_KEY")
        return False


def verify_database():
    """Verify database is accessible."""
    import sqlite3
    
    db_path = os.getenv("DATABASE_PATH", "./data/chinook.db")
    
    if not Path(db_path).exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    print(f"Verifying database at {db_path}...", end=" ")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        print(f"✓ Found {len(tables)} tables")
        return True
    except Exception as e:
        print("❌ FAILED")
        print(f"  Error: {e}")
        return False


def install_dependencies():
    """Check if dependencies need to be installed."""
    print("\nTo install dependencies, run:")
    print("  pip install -r requirements.txt")
    print("")


def main():
    print_header()
    
    all_ok = True
    
    # Check Python version
    if not check_python_version():
        all_ok = False
    
    # Create directories
    create_directories()
    
    # Download database
    if not download_chinook_database():
        all_ok = False
    
    # Create .env file
    create_env_file()
    
    print("")
    
    # Try to load dotenv and check API key
    try:
        if not check_api_key():
            all_ok = False
    except ImportError:
        print("⚠️  python-dotenv not installed yet")
    
    # Verify database
    try:
        from dotenv import load_dotenv
        load_dotenv()
        verify_database()
    except ImportError:
        print("⚠️  Dependencies not installed yet")
    
    # Show next steps
    install_dependencies()
    
    print("=" * 60)
    if all_ok:
        print("✅ Setup complete! You can now run:")
        print("   python cli.py")
        print("   or")
        print("   streamlit run ui/streamlit_app.py")
    else:
        print("⚠️  Setup incomplete. Please resolve the issues above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
