# Streamlit Legacy Frontend

> **⚠️ DEPRECATED**: This frontend is maintained for backward compatibility only.  
> **Use the new Next.js frontend at `frontend-next/` instead.**

## Why Deprecated?

The Streamlit frontend was the original demo UI for ReasonSQL. It has been replaced with a modern Next.js frontend that:

- Runs as a standalone app (no Python required)
- Has better performance and loading times  
- Provides a more polished user experience
- Separates concerns (pure API client, no backend code)

## Still Want to Run It?

```bash
# From project root, with FastAPI running:
cd frontend/streamlit_legacy
python -m streamlit run streamlit_app.py
```

## Files

- `streamlit_app.py` - Main Streamlit application (1700+ lines)
- `api_client.py` - HTTP client for FastAPI backend

## Migration Notes

The Streamlit app now supports **API Mode** - toggle in sidebar to route queries through FastAPI instead of direct orchestrator calls. This was the bridge during migration.

---

**For active development, use `frontend-next/` instead.**
