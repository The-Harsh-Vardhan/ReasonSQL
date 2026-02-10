# ⚡ Vercel + Supabase Quick Setup (5 Minutes)

## 🎯 What You're Setting Up
Direct integration: **Vercel (Frontend + Database) ↔ Supabase (PostgreSQL)**  
Region: **Mumbai, India (bom1)** for lowest latency

---

## ✅ Step-by-Step Checklist

### 1️⃣ Create Database in Vercel (You're here!)
- [ ] In Vercel Dashboard, you see "Create Database" screen
- [ ] Primary Region: **Mumbai, India (South)** ✅ (Already selected)
- [ ] Prefix: `NEXT_PUBLIC_` ✅ (Keep default)
- [ ] Click **"Create Database"**
- [ ] Wait ~30 seconds for provisioning

### 2️⃣ Note Your Credentials (Auto-generated)
After creation, go to: **Vercel Project → Settings → Environment Variables**

You'll see these auto-created:
```
POSTGRES_URL                    # Full connection string
SUPABASE_URL                    # https://xxxxx.supabase.co
SUPABASE_ANON_KEY              # Public key (safe for client)
SUPABASE_SERVICE_ROLE_KEY      # Secret key (server only!)
```

✅ **No action needed** - Vercel injects these automatically!

### 3️⃣ Initialize Database Schema
1. In Vercel, click **"Go to Supabase Dashboard"** (or from Vercel → Storage → Supabase)
2. In Supabase Dashboard → **SQL Editor**
3. Click **"New Query"**
4. Copy entire content from `scripts/supabase_setup.sql`
5. Paste and click **"Run"** (or `Ctrl+Enter`)
6. Verify in **Table Editor** → You should see tables: Artist, Album, Customer, etc.

### 4️⃣ Choose Your Architecture

#### Option A: Keep Render Backend (Easiest - 2 minutes)
**Best if**: You want minimal changes

1. Copy `POSTGRES_URL` from Vercel Environment Variables
2. Go to Render Dashboard → Your Service → Environment
3. Update `DATABASE_URL` = `<paste POSTGRES_URL>`
4. Click "Save" → Auto-redeploys in ~2 min
5. ✅ Done! Test a query from your frontend

#### Option B: Move Backend to Vercel (Advanced - 30 minutes)
**Best if**: You want everything in Vercel ecosystem

See full guide: [docs/VERCEL_SUPABASE_SETUP.md](docs/VERCEL_SUPABASE_SETUP.md#option-b-move-backend-to-vercel-full-integration)

---

## 🔥 Quick Commands

### Test Database Connection (Supabase SQL Editor)
```sql
SELECT "Name" FROM "Artist" LIMIT 5;
```
Expected: List of 5 artist names

### Redeploy Vercel (if needed)
```bash
cd frontend-next
vercel --prod
```

### Check Environment Variables
```bash
# In Vercel Dashboard → Settings → Environment Variables
# or via CLI:
vercel env ls
```

---

## 🚀 What Changed?

### Before (Old Architecture)
```
User → Vercel (Next.js) → Render (FastAPI) → SQLite (on Render disk)
                                           ↓
                                    Supabase (unused)
```

### After (New Architecture - Option A)
```
User → Vercel (Next.js) → Render (FastAPI) → Supabase PostgreSQL (Mumbai)
       ↑__________________________|
       (Direct DB access possible)
```

### After (New Architecture - Option B)
```
User → Vercel (Next.js + API Routes) → Supabase PostgreSQL (Mumbai)
       └─ All in Mumbai region for 10-20ms latency
```

---

## 📊 Environment Variables Reference

### What Vercel Auto-Injects (After DB creation)
| Variable | Purpose | Where to Use |
|----------|---------|--------------|
| `POSTGRES_URL` | Full connection string | Backend (Render/Vercel) |
| `POSTGRES_PRISMA_URL` | Connection pooling | If using Prisma |
| `POSTGRES_URL_NON_POOLING` | Direct connections | Migrations |
| `SUPABASE_URL` | Supabase API endpoint | Frontend/Backend |
| `SUPABASE_ANON_KEY` | Public API key | Frontend (safe) |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin API key | Backend only (secret!) |

### What You Need to Add to Render (Option A)
| Variable | Value | Where to Get |
|----------|-------|--------------|
| `DATABASE_URL` | Copy `POSTGRES_URL` | Vercel → Env Variables |
| `ALLOWED_ORIGINS` | Your Vercel domain | e.g., `https://reasonsql.vercel.app` |

---

## ✨ Benefits You Just Unlocked

1. **🚀 Better Performance**: Mumbai → Mumbai (not Mumbai → Oregon → Mumbai)
2. **💰 Cost Savings**: Free Supabase tier (500 MB, 2GB transfer/month)
3. **🔄 Real-time Ready**: Supabase realtime subscriptions available
4. **📈 Scalability**: Auto-scaling database
5. **🛡️ Built-in Auth**: Supabase Auth (if needed later)
6. **💾 Auto Backups**: Daily backups (7-day retention on free tier)

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Database not found" | Redeploy Vercel after creating database |
| "relation does not exist" | Run `supabase_setup.sql` in Supabase SQL Editor |
| CORS errors | Add Vercel domain to Supabase Settings → API → Allowed Origins |
| Slow queries | Check regions match (both Mumbai) |
| Env vars missing | Go to Vercel → Settings → Redeploy |

---

## 📚 Full Documentation

For detailed guides and advanced setups:
- **Full Setup Guide**: [docs/VERCEL_SUPABASE_SETUP.md](docs/VERCEL_SUPABASE_SETUP.md)
- **Original Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **SQL Schema**: [scripts/supabase_setup.sql](scripts/supabase_setup.sql)

---

## ✅ Success Criteria

You're done when:
- [ ] Supabase database shows "Active" in Vercel
- [ ] SQL Editor query returns artist names
- [ ] Environment variables visible in Vercel settings
- [ ] Backend connects successfully (check logs)
- [ ] Frontend query returns results

**Test Query from Frontend:**
```
User: "Show me 5 artists"
Expected: Table with 5 artist names
```

---

**Need help?** Check the full guide or your deployment logs!
