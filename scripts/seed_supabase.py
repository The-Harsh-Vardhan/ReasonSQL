"""
Test and seed Supabase connection with Chinook data.
Run: python scripts/seed_supabase.py
"""
import os
import sys

# URL-encode the @ in password
DB_URL = "postgresql://postgres.cycbtnettmqkoszqepld:ReasonSQL2026%40Secure!@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"

def run():
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("Installing psycopg2-binary...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
        import psycopg2
        from psycopg2.extras import RealDictCursor

    print("[1] Connecting to Supabase (Singapore)...")
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        conn.autocommit = True
        cursor = conn.cursor()
        print("[✓] Connected!")
    except Exception as e:
        print(f"[✗] Connection failed: {e}")
        sys.exit(1)

    # Check current tables
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    tables = [row["table_name"] for row in cursor.fetchall()]
    print(f"[2] Current tables ({len(tables)}): {tables}")

    if len(tables) == 0:
        print("[!] No tables found — schema not applied yet. Run: supabase db push")
        conn.close()
        sys.exit(1)

    # Check if Artist table has data
    cursor.execute('SELECT COUNT(*) as cnt FROM "Artist"')
    artist_count = cursor.fetchone()["cnt"]
    print(f"[3] Artist rows: {artist_count}")

    if artist_count > 0:
        print("[✓] Data already seeded! Verifying all tables...")
    else:
        print("[4] Seeding Chinook data...")
        seed_path = os.path.join(os.path.dirname(__file__), "..", "supabase", "seed.sql")
        with open(seed_path, "r", encoding="utf-8") as f:
            seed_sql = f.read()
        try:
            cursor.execute(seed_sql)
            print("[✓] Seed data applied!")
        except Exception as e:
            print(f"[✗] Seeding failed: {e}")
            conn.close()
            sys.exit(1)

    # Final verification
    tables_to_check = ["Artist", "Album", "Track", "Customer", "Invoice", "InvoiceLine", "Genre", "Employee", "MediaType", "Playlist", "PlaylistTrack"]
    print("\n[5] Table counts:")
    for table in tables_to_check:
        try:
            cursor.execute(f'SELECT COUNT(*) as cnt FROM "{table}"')
            count = cursor.fetchone()["cnt"]
            status = "✓" if count > 0 else "✗ EMPTY"
            print(f"    {status}  {table}: {count} rows")
        except Exception as e:
            print(f"    ✗  {table}: {e}")

    conn.close()
    print("\n[✓] Done! Supabase Chinook database is ready.")

if __name__ == "__main__":
    run()
