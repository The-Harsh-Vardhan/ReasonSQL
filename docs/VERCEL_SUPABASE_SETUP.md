# 🚀 Vercel + Supabase Direct Integration Guide

This guide shows how to set up Supabase directly in Vercel, eliminating the need for Render as an intermediary.

## 📋 Architecture Options

### Option 1: Vercel + Supabase (Recommended)
- Frontend: Vercel (Next.js)
- Database: Supabase PostgreSQL
- Backend API: Vercel Serverless Functions
- ✅ All in one ecosystem, automatic env syncing

### Option 2: Hybrid Approach
- Frontend: Vercel (Next.js)
- Database: Supabase PostgreSQL
- Backend API: Render (FastAPI) → connects to Supabase
- ✅ Keep existing backend, just migrate database

---

## 🟢 Step 1: Create Supabase Database in Vercel

You're already on this screen! Here's what to do:

### 1.1 Configure Database Settings
Based on your screenshot:
- **Primary Region**: Mumbai, India (South) ✅ (Already selected)
- **Public Environment Variables Prefix**: `NEXT_PUBLIC_` ✅ (Keep default)

### 1.2 Complete Database Creation
1. Click "Create Database" or "Continue"
2. Vercel will automatically:
   - Create a new Supabase project
   - Generate database credentials
   - Inject environment variables into your Vercel project

### 1.3 Environment Variables Auto-Created
After creation, you'll automatically get:
```env
# Supabase Connection (Auto-injected by Vercel)
POSTGRES_URL="postgres://..."
POSTGRES_PRISMA_URL="postgres://..."
POSTGRES_URL_NON_POOLING="postgres://..."
SUPABASE_URL="https://xxxxx.supabase.co"
SUPABASE_ANON_KEY="eyJhbGc..."
SUPABASE_SERVICE_ROLE_KEY="eyJhbGc..." # Keep secret!
```

---

## 🔷 Step 2: Initialize Database Schema

### 2.1 Open Supabase Dashboard
1. Go to Vercel Dashboard → Your Project → Storage tab
2. Click "Go to Supabase Dashboard"
3. Navigate to **SQL Editor**

### 2.2 Run Setup Script
Copy and paste the entire contents of your `scripts/supabase_setup.sql`:

```bash
# The script creates all Chinook database tables and sample data
# Located at: scripts/supabase_setup.sql
```

1. In Supabase SQL Editor, click "New Query"
2. Paste the entire SQL script from `scripts/supabase_setup.sql`
3. Click "Run" or press `Ctrl+Enter`
4. Verify tables were created in the "Table Editor" tab

---

## 🟣 Step 3: Update Your Application

### Option A: Keep Render Backend (Easier Migration)

Update your Render backend to use Supabase:

#### 3.A.1 Update `render.yaml`
```yaml
envVars:
  # Replace DATABASE_URL with your Supabase connection
  - key: DATABASE_URL
    value: postgres://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
    
  # OR sync from Vercel (recommended)
  - key: DATABASE_URL
    sync: false  # Set manually in Render dashboard
```

#### 3.A.2 Add Environment Variable in Render
1. Go to Render Dashboard → Your Service
2. Navigate to "Environment" tab
3. Add `DATABASE_URL` from Supabase (found in Supabase Settings → Database)
4. Click "Save Changes" → Service will auto-redeploy

#### 3.A.3 Update `vercel.json` (Frontend)
No changes needed! Your proxy to Render backend still works:
```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://reasonsql-api.onrender.com/:path*"
    }
  ]
}
```

---

### Option B: Move Backend to Vercel (Full Integration)

Move your FastAPI backend to Vercel Serverless Functions:

#### 3.B.1 Create API Routes in Next.js
Create `frontend-next/app/api/query/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

// Supabase client (auto-configured by Vercel)
const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_ANON_KEY!
);

export async function POST(request: NextRequest) {
  try {
    const { query } = await request.json();
    
    // Call your Python agent logic here
    // (You'll need to port Python logic to TypeScript or use Python runtime)
    
    const { data, error } = await supabase.rpc('your_rpc_function', { 
      user_query: query 
    });
    
    if (error) throw error;
    
    return NextResponse.json({ success: true, data });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
```

#### 3.B.2 Install Supabase Client
```bash
cd frontend-next
npm install @supabase/supabase-js
```

#### 3.B.3 Update `vercel.json`
Remove the Render proxy, use local API routes:
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "regions": ["bom1"],  // Mumbai (matches your Supabase region)
  "env": {
    "NEXT_PUBLIC_API_URL": "/api"  // Local API routes
  }
}
```

---

## 🔧 Step 4: Update Database Adapter

Update `backend/db_connection.py` to use PostgreSQL:

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use Supabase PostgreSQL instead of SQLite
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found. Set up Supabase connection.")

# Create PostgreSQL engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 🎯 Step 5: Deployment Checklist

### For Option A (Render + Supabase)
- [ ] Created Supabase database in Vercel
- [ ] Ran `supabase_setup.sql` in Supabase SQL Editor
- [ ] Copied `DATABASE_URL` from Supabase Dashboard
- [ ] Updated `DATABASE_URL` in Render environment variables
- [ ] Verified Render service redeployed successfully
- [ ] Tested query from frontend

### For Option B (Full Vercel)
- [ ] Created Supabase database in Vercel
- [ ] Ran `supabase_setup.sql` in Supabase SQL Editor
- [ ] Created API routes in Next.js
- [ ] Installed `@supabase/supabase-js`
- [ ] Updated `vercel.json` regions to `["bom1"]` (Mumbai)
- [ ] Redeployed frontend to Vercel
- [ ] Tested queries end-to-end

---

## 🔍 Verification

### Test Database Connection

#### From Supabase Dashboard:
1. Go to Table Editor
2. Open any table (e.g., `Artist`)
3. Verify data is present

#### From Your Application:
```bash
# Test query to verify connection
SELECT "Name" FROM "Artist" LIMIT 5;
```

Expected result: List of artist names from Chinook database

---

## 📊 Environment Variables Summary

### Vercel (Auto-injected after Supabase setup)
```env
POSTGRES_URL=postgres://...
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...  # SECRET!
NEXT_PUBLIC_API_URL=/api  # or https://reasonsql-api.onrender.com
```

### Render (If keeping backend there)
```env
DATABASE_URL=postgres://...  # From Supabase
GEMINI_API_KEY=AIzaSy...
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-2.0-flash-exp
ALLOWED_ORIGINS=https://your-project.vercel.app
```

---

## ⚡ Advantages of Direct Vercel + Supabase

1. **Automatic Env Sync**: No manual copying of credentials
2. **Same Region**: Deploy both in Mumbai for lowest latency
3. **Better DX**: Single dashboard for frontend + database
4. **Real-time Ready**: Built-in subscriptions and realtime features
5. **Scalability**: Auto-scaling for both compute and database
6. **Cost**: Free tier covers most development/small production use

---

## 🚨 Troubleshooting

### Issue: "relation does not exist"
**Solution**: Run `supabase_setup.sql` script in Supabase SQL Editor

### Issue: Connection timeout
**Solution**: Check region mismatch. Set Vercel regions to match Supabase:
```json
"regions": ["bom1"]  // Mumbai
```

### Issue: Environment variables not found
**Solution**: Redeploy Vercel project after database creation:
```bash
vercel --prod
```

### Issue: CORS errors
**Solution**: Add your Vercel domain to Supabase allowed origins:
1. Supabase Dashboard → Settings → API
2. Add `https://your-project.vercel.app` to allowed origins

---

## 📚 Next Steps

1. **Enable Row Level Security (RLS)** for production:
   - Supabase Dashboard → Authentication → Policies
   
2. **Set up GitHub Actions** for automated deployments:
   - Vercel auto-deploys on push to `main`
   
3. **Monitor Performance**:
   - Supabase Dashboard → Reports
   - Vercel Dashboard → Analytics

4. **Backup Strategy**:
   - Supabase automatic daily backups (free tier: 7 days retention)
   - Consider scheduled exports for critical data

---

## 📖 Resources

- [Vercel + Supabase Integration Docs](https://vercel.com/docs/integrations/supabase)
- [Supabase PostgreSQL Docs](https://supabase.com/docs/guides/database)
- [Next.js API Routes](https://nextjs.org/docs/app/building-your-application/routing/route-handlers)
- Your existing setup script: `scripts/supabase_setup.sql`

---

## 🎉 Done!

You now have a modern, scalable architecture:
- ✅ No intermediary services (direct Vercel ↔ Supabase)
- ✅ Auto-synced environment variables
- ✅ Same region deployment for low latency
- ✅ Production-ready PostgreSQL database
