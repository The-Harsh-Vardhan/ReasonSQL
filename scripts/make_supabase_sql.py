"""Convert Chinook_PostgreSql.sql to Supabase-compatible version."""
import re

with open(r"c:\My Drive\Projects\ReasonSQL\data\Chinook_PostgreSql.sql", "r", encoding="utf-8") as f:
    content = f.read()

# Remove DROP DATABASE, CREATE DATABASE, \c lines
content = re.sub(r"(?m)^DROP DATABASE.*$", "-- (removed for Supabase)", content)
content = re.sub(r"(?m)^CREATE DATABASE.*$", "-- (removed for Supabase)", content)
content = re.sub(r"(?m)^\\c.*$", "-- (removed for Supabase)", content)

header = """-- =============================================================
-- Chinook Database for Supabase (auto-generated)
-- =============================================================
-- Drop old PascalCase tables (from previous supabase_setup.sql)
DROP TABLE IF EXISTS "PlaylistTrack" CASCADE;
DROP TABLE IF EXISTS "InvoiceLine" CASCADE;
DROP TABLE IF EXISTS "Invoice" CASCADE;
DROP TABLE IF EXISTS "Track" CASCADE;
DROP TABLE IF EXISTS "Playlist" CASCADE;
DROP TABLE IF EXISTS "MediaType" CASCADE;
DROP TABLE IF EXISTS "Genre" CASCADE;
DROP TABLE IF EXISTS "Customer" CASCADE;
DROP TABLE IF EXISTS "Employee" CASCADE;
DROP TABLE IF EXISTS "Album" CASCADE;
DROP TABLE IF EXISTS "Artist" CASCADE;

-- Drop snake_case tables (in case re-running)
DROP TABLE IF EXISTS playlist_track CASCADE;
DROP TABLE IF EXISTS invoice_line CASCADE;
DROP TABLE IF EXISTS invoice CASCADE;
DROP TABLE IF EXISTS track CASCADE;
DROP TABLE IF EXISTS playlist CASCADE;
DROP TABLE IF EXISTS media_type CASCADE;
DROP TABLE IF EXISTS genre CASCADE;
DROP TABLE IF EXISTS customer CASCADE;
DROP TABLE IF EXISTS employee CASCADE;
DROP TABLE IF EXISTS album CASCADE;
DROP TABLE IF EXISTS artist CASCADE;

"""

with open(r"c:\My Drive\Projects\ReasonSQL\data\Chinook_Supabase.sql", "w", encoding="utf-8") as f:
    f.write(header + content)

print("Done! Created data/Chinook_Supabase.sql")
