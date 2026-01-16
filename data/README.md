# Data Directory

This directory is used to store the SQLite database files.

## Chinook Database

The project uses the **Chinook Database** - a sample database representing a digital media store. It includes:

### Tables (11)
| Table | Description |
|-------|-------------|
| `Artist` | Music artists |
| `Album` | Albums with artist references |
| `Track` | Individual tracks with album, genre, and media type |
| `Genre` | Music genres (Rock, Jazz, etc.) |
| `MediaType` | Audio format types |
| `Playlist` | Named playlists |
| `PlaylistTrack` | Tracks in playlists (many-to-many) |
| `Customer` | Customer information |
| `Employee` | Store employees |
| `Invoice` | Customer purchases |
| `InvoiceLine` | Individual items in invoices |

### Setup

The database is automatically downloaded by running:

```bash
python setup.py
```

Or you can manually download it from:
- https://github.com/lerocha/chinook-database

### Note

- **Do not commit** actual database files to Git
- The `.gitignore` excludes `*.db` files from this directory
- Only this README and `.gitkeep` are tracked
