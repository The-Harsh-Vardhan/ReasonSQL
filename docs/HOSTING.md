# 🌐 Hosting Guide: ReasonSQL

This guide explains how to deploy the ReasonSQL multi-agent system to production using **Supabase** (Database), **Render** (Backend), and **Vercel** (Frontend).

---

## 🏗️ Architecture Overview

```mermaid
graph TD
    A[Vercel - Next.js] -- "POST /query" --> B[Render - FastAPI]
    B -- "SQL Execution" --> C[Supabase - PostgreSQL]
    B -- "Reasoning" --> D[LLM Providers]
```

---

## 1. 🗄️ Database Setup (Supabase)

1. **Create Project**: Sign up at [Supabase](https://supabase.com) and create a new project.
2. **Region**: Choose a region close to your users (e.g., Mumbai, India).
3. **Run SQL Script**:
   - Go to the **SQL Editor** in the Supabase dashboard.
   - Click **+ New Query**.
   - Paste the contents of your database setup script (typically found in `Extras/scripts/supabase_setup.sql`).
   - Click **Run**.
4. **Get Connection String**:
   - Go to **Settings** → **Database**.
   - Copy the **Connection URI** (PostgreSQL URL). It looks like:
     `postgresql://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres`

---

## 2. ⚡ Backend Deployment (Render)

1. **Create Web Service**:
   - Dashboard → **New** → **Web Service**.
   - Connect your GitHub repository.
2. **Configuration**:
   - **Runtime**: `Python 3.10+`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 10000`
3. **Environment Variables**:
   | Variable | Value |
   |----------|-------|
   | `GEMINI_API_KEY` | Your Google Gemini API key |
   | `DATABASE_URL` | Your Supabase connection string from Step 1 |
   | `LLM_PROVIDER` | `gemini` |
   | `ALLOWED_ORIGINS` | `https://your-frontend-url.vercel.app` |
   | `QUERY_TIMEOUT_SECONDS` | `120` (Optional) |
   | `LOG_LEVEL` | `INFO` (Optional) |

---

## 3. 🎨 Frontend Deployment (Vercel)

1. **Create Project**:
   - Go to [Vercel](https://vercel.com) and click **Add New** → **Project**.
   - Connect your GitHub repository.
2. **Configuration**:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: `frontend-next`
3. **Environment Variables**:
   | Variable | Value |
   |----------|-------|
   | `NEXT_PUBLIC_API_URL` | Your Render backend URL (e.g., `https://reasonsql-api.onrender.com`) |
4. **Deploy**: Click **Deploy**.

---

## 🧪 Testing Your Deployment

1. Visit your Vercel URL.
2. Check the **System Status** in the sidebar. Both **API** and **Database** should show green indicators.
3. Try a simple query: *"How many customers are from Brazil?"*
4. Verify the **Reasoning Trace** and **Data Preview** appear correctly.

---

## 🛠️ Maintenance & Scaling

- **Gemini Quota**: If you hit rate limits, ensure you have multiple keys or credit in your Google AI Studio account.
- **Render Sleep**: On the free tier, Render services go to sleep after 15 mins of inactivity. The first query after wake-up may take ~30 seconds.
- **Database Backups**: Supabase handles automatic backups on the free tier (7-day retention).
