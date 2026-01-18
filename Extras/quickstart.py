#!/usr/bin/env python3
"""
Quick Start Script for NL2SQL Multi-Agent System.

This script performs a complete setup and runs a demonstration:
1. Checks Python version
2. Downloads Chinook database
3. Validates configuration
4. Runs sample queries

Usage:
    python quickstart.py
"""
import os
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))


def print_banner():
    """Print welcome banner."""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║         🔍 NL2SQL Multi-Agent System - Quick Start                    ║
║         ─────────────────────────────────────────────                 ║
║         Natural Language to SQL with 12 Intelligent Agents            ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)


def check_environment():
    """Check Python version and dependencies."""
    print("🔍 Checking environment...")
    
    # Python version
    if sys.version_info < (3, 10):
        print(f"❌ Python 3.10+ required (found {sys.version})")
        return False
    print(f"   ✓ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check critical imports
    try:
        import crewai
        print(f"   ✓ CrewAI {crewai.__version__ if hasattr(crewai, '__version__') else 'installed'}")
    except ImportError:
        print("   ❌ CrewAI not installed. Run: pip install -r requirements.txt")
        return False
    
    try:
        import rich
        print("   ✓ Rich terminal formatting")
    except ImportError:
        print("   ❌ Rich not installed. Run: pip install -r requirements.txt")
        return False
    
    try:
        from dotenv import load_dotenv
        print("   ✓ python-dotenv")
    except ImportError:
        print("   ❌ python-dotenv not installed. Run: pip install -r requirements.txt")
        return False
    
    return True


def setup_database():
    """Download and setup Chinook database."""
    print("\n📦 Setting up database...")
    
    from setup import download_chinook_database, create_directories
    create_directories()
    
    if download_chinook_database():
        print("   ✓ Chinook database ready")
        return True
    return False


def check_api_key():
    """Check if API key is configured."""
    print("\n🔑 Checking API configuration...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    groq_key = os.getenv("GROQ_API_KEY", "")
    google_key = os.getenv("GOOGLE_API_KEY", "")
    
    # Check for placeholder values
    placeholders = ["your_groq_api_key_here", "gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", ""]
    
    if groq_key and groq_key not in placeholders:
        print("   ✓ Groq API key configured")
        return True
    
    if google_key and google_key not in ["your_google_api_key_here", "AIzaSy_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", ""]:
        print("   ✓ Google API key configured")
        return True
    
    print("   ⚠️  No API key configured!")
    print("\n   To fix this:")
    print("   1. Get a free Groq API key from: https://console.groq.com/keys")
    print("   2. Copy .env.example to .env: cp .env.example .env")
    print("   3. Edit .env and add your API key")
    print("   4. Run this script again")
    return False


def run_demo_queries():
    """Run a few demonstration queries."""
    print("\n🎮 Running demonstration queries...\n")
    
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    
    console = Console()
    
    try:
        from orchestrator import NL2SQLOrchestrator
        orchestrator = NL2SQLOrchestrator(verbose=False)
        
        # Demo queries
        queries = [
            ("Simple Query", "How many customers are from Brazil?"),
            ("Meta Query", "What tables exist in this database?"),
            ("Join Query", "List all albums by AC/DC"),
        ]
        
        for category, query in queries:
            console.print(f"\n[bold cyan]━━━ {category} ━━━[/bold cyan]")
            console.print(f"[dim]Query:[/dim] {query}")
            
            try:
                response = orchestrator.process_query(query)
                
                # Show SQL if available
                if response.sql_used and response.sql_used != "N/A":
                    console.print("[dim]SQL:[/dim]")
                    console.print(Syntax(response.sql_used, "sql", theme="monokai"))
                
                # Show answer
                console.print(Panel(response.answer, title="Answer", border_style="green"))
                
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        return True
        
    except Exception as e:
        print(f"❌ Error running demo: {e}")
        return False


def print_next_steps():
    """Print next steps for the user."""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                         ✅ Quick Start Complete!                      ║
╚═══════════════════════════════════════════════════════════════════════╝

🚀 Next Steps:

   Interactive Mode:     python cli.py
   Single Query:         python cli.py -q "Your question here"
   Full Demo:            python demo.py
   Web Interface:        streamlit run ui/streamlit_app.py

📖 Documentation:

   README.md             - Full documentation and architecture
   CONTRIBUTING.md       - How to contribute
   examples/             - Reasoning trace examples

🔗 Useful Links:

   Groq Console:         https://console.groq.com/keys
   CrewAI Docs:          https://docs.crewai.com/
   Chinook Schema:       https://github.com/lerocha/chinook-database

Happy querying! 🎉
""")


def main():
    """Run quick start process."""
    print_banner()
    
    # Step 1: Check environment
    if not check_environment():
        print("\n❌ Environment check failed. Please install dependencies first:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    
    # Step 2: Setup database
    if not setup_database():
        print("\n❌ Database setup failed.")
        sys.exit(1)
    
    # Step 3: Check API key
    if not check_api_key():
        print("\n⚠️  Skipping demo - configure API key first.")
        sys.exit(0)
    
    # Step 4: Run demo
    if run_demo_queries():
        print_next_steps()
    else:
        print("\n⚠️  Demo had some issues, but setup is complete.")
        print("   Try running: python cli.py")


if __name__ == "__main__":
    main()
