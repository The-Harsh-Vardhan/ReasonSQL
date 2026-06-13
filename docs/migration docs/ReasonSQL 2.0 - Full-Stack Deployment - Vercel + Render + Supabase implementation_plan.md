# ReasonSQL 2.0 — Full-Stack Deployment: Vercel + Render + Supabase

Connect the ReasonSQL 2.0 frontend (Next.js) to the backend (FastAPI), with the Chinook database seeded on Supabase. The infrastructure already has scaffolding in place (`render.yaml`, `vercel.json`, `.vercel/project.json`), so this is mostly a wiring + verification task.

## Current State

| Component | Status |
|-----------|--------|
| **Frontend** | Next.js app in `frontend-next/`, `.vercel/project.json` exists (already linked to Vercel project `frontend-next`) |
| **Backend** | FastAPI in `backend/api/main.py`, `render.yaml` exists |
| **Database** | Supabase project `reasonsql-prod` (Singapore) referenced in `render.yaml` comments; `supabase/seed.sql` + schema migrations exist |
| **CORS** | `render.yaml` ALLOWED_ORIGINS already includes Vercel URLs |
| **Proxy** | `vercel.json` rewrites `/api/*` → `https://reasonsql-api-rl3g.onrender.com/*` |

## Open Questions

> [!IMPORTANT]
> **These need to be confirmed before proceeding:**
> 1. **Supabase DATABASE_URL** — Is the Supabase project already created? Do you have the connection string (pooler URL + password)? The render.yaml references it but has `<PASSWORD>` placeholder.
> 2. **Render service** — Is `reasonsql-api-rl3g.onrender.com` already deployed and configured, or does it need to be created from scratch?
> 3. **Vercel project** — The `.vercel/project.json` shows project name `frontend-next` (ID `prj_wbVbONNPjDu9aVORfiH7AAWvd3NE`). Is it already deployed at `reason-sql.vercel.app`?
> 4. **API Keys on Render** — Are the Gemini API keys already set in the Render dashboard, or do they need to be added?

## Proposed Changes

### Phase 1 — Supabase Database Setup

If the Supabase schema is not yet created:

#### Run Migrations + Seed
- Run the SQL in `supabase/migrations/` to create the Chinook schema (11 tables)
- Run `supabase/seed.sql` to populate the data
- These can be run via the Supabase SQL editor or `psql`

### Phase 2 — Render Backend

The `render.yaml` is already configured. The main task is:

#### Set Environment Variables in Render Dashboard
```
DATABASE_URL = postgresql://postgres.cycbtnettmqkoszqepld:<PASSWORD>@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres
GEMINI_API_KEY = <from .env>
GEMINI_API_KEY_1..4 = <from .env>
GROQ_API_KEY = <from .env>
ALLOWED_ORIGINS = https://reason-sql.vercel.app,https://reasonsql.vercel.app
```

#### [MODIFY] [render.yaml](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/render.yaml)
- Verify `buildCommand` and `startCommand` are correct
- Ensure `healthCheckPath: /health` is set (it is)

### Phase 3 — Vercel Frontend

The `.vercel/project.json` already links to the Vercel project. The main task is:

#### [MODIFY] [vercel.json](file:///c:/D%20Drive/Projects/6th%20Sem/ReasonSQL/frontend-next/vercel.json)
- Verify the rewrite points to the correct Render URL
- Set `NEXT_PUBLIC_API_URL` to `/api` (already done)

#### Deploy via Vercel CLI
```bash
cd frontend-next
vercel --prod
```

### Phase 4 — Code Fixes (if needed)

Based on code analysis, there may be issues to address:

1. **`configs/settings.py` imports at module level** — `db_connection.py` creates engine at import time, which means any `DATABASE_URL` misconfiguration crashes at startup. This is acceptable for production but requires correct env vars.

2. **`render.yaml` build command** — Uses `pip install -r backend/requirements.txt` but the root `requirements.txt` is the complete one. May need to align.

3. **`NEXT_PUBLIC_API_URL` env var** — Should be set to `/api` in Vercel project settings (the rewrite handles proxying to Render).

### Phase 5 — End-to-End Testing

After deployment:

1. Hit `https://reasonsql-api-rl3g.onrender.com/health` → should return `{connected: true}`
2. Hit `https://reason-sql.vercel.app` → frontend should load
3. Run a test query: "How many customers are from Brazil?" → should return 5
4. Check schema explorer loads in sidebar
5. Test file upload modal

## Verification Plan

### Automated Tests
- `GET /health` on Render URL
- `POST /query` with `{"query": "How many customers are there?"}` 

### Manual Verification
- Frontend loads at Vercel URL
- Query returns answer with reasoning trace
- SQL is shown with syntax highlighting
- Data preview table renders
- System status in sidebar shows "Connected"
