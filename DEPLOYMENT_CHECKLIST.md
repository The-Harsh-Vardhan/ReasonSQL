# 🚀 Deployment Checklist

Use this checklist before deploying to ensure everything is ready.

## ✅ Pre-Deployment Checklist

### 🔐 Security & Secrets

- [ ] No API keys in code files
- [ ] `.env` file is in `.gitignore`
- [ ] `.streamlit/secrets.toml` is in `.gitignore`
- [ ] `.env.example` has placeholder values only
- [ ] `.streamlit/secrets.toml.example` exists with placeholders
- [ ] All secret files are properly documented

### 📦 Dependencies

- [ ] `requirements.txt` is up to date
- [ ] All imports work correctly
- [ ] `packages.txt` includes system dependencies (if any)
- [ ] Docker builds successfully: `docker build -t nl2sql-test .`
- [ ] Docker container runs: `docker run -p 8501:8501 nl2sql-test`

### 🗄️ Database

- [ ] `data/chinook.db` exists in repository
- [ ] Database path is configurable via environment variable
- [ ] `setup.py` downloads database if missing
- [ ] Database is read-only in production

### 🎨 Streamlit Configuration

- [ ] `.streamlit/config.toml` exists with proper theme
- [ ] Streamlit app runs locally: `streamlit run ui/streamlit_app.py`
- [ ] All features work in the UI
- [ ] Demo mode works
- [ ] No hardcoded secrets in `ui/streamlit_app.py`

### 📝 Documentation

- [ ] `README.md` is clear and accurate
- [ ] `DEPLOYMENT.md` exists with step-by-step instructions
- [ ] `CONTRIBUTING.md` is up to date
- [ ] All badges in README are correct
- [ ] License file exists

### 🧪 Testing

- [ ] Demo mode runs: `python cli.py --demo`
- [ ] CLI works: `python cli.py -q "test query"`
- [ ] Web UI launches without errors
- [ ] All 5 demo queries execute successfully
- [ ] Error handling works (test with invalid queries)

### 🐳 Docker Deployment

- [ ] `Dockerfile` exists and builds
- [ ] `docker-compose.yml` exists
- [ ] `.dockerignore` excludes unnecessary files
- [ ] Health checks work
- [ ] Environment variables are properly passed

### ☁️ Streamlit Cloud Specific

- [ ] Repository is public (or you have a Streamlit Cloud paid plan)
- [ ] Main file path is `ui/streamlit_app.py`
- [ ] Python version is 3.10+ in `runtime.txt` (if needed)
- [ ] All secrets documented in deployment guide
- [ ] App has proper title and description

### 🔍 GitHub Repository

- [ ] `.gitignore` properly excludes sensitive files
- [ ] `.github/workflows/` has CI/CD pipelines (optional but recommended)
- [ ] Repository has proper description
- [ ] Topics/tags are added for discoverability
- [ ] README badges are functional
- [ ] License is specified

## 📋 Deployment Steps

### For Streamlit Cloud:

1. ✅ Complete all checklist items above
2. Push code to GitHub
3. Sign in to [share.streamlit.io](https://share.streamlit.io)
4. Click "New app"
5. Select repository and branch
6. Set main file: `ui/streamlit_app.py`
7. Add secrets from `.streamlit/secrets.toml.example`
8. Click "Deploy!"

### For Docker:

1. ✅ Complete all checklist items above
2. Build: `docker build -t nl2sql-multiagent .`
3. Run: `docker run -p 8501:8501 -e GROQ_API_KEY=your_key nl2sql-multiagent`
4. Or use: `docker-compose up`

### For Local:

1. ✅ Complete all checklist items above
2. Setup: `pip install -r requirements.txt`
3. Configure: `cp .env.example .env` and add keys
4. Run: `streamlit run ui/streamlit_app.py`

## 🐛 Common Issues & Solutions

### Issue: "ModuleNotFoundError"
**Solution:** Run `pip install -r requirements.txt`

### Issue: "API Key not configured"
**Solution:** 
- Local: Check `.env` file has valid API key
- Streamlit Cloud: Check secrets are properly set in dashboard
- Docker: Pass environment variables: `-e GROQ_API_KEY=your_key`

### Issue: "Database not found"
**Solution:** Run `python setup.py` to download database

### Issue: Docker build fails
**Solution:** Check `.dockerignore` and ensure all required files are included

### Issue: Streamlit Cloud deployment fails
**Solution:** 
- Check logs in Streamlit Cloud dashboard
- Verify all imports work
- Check requirements.txt syntax

## 🎉 Post-Deployment

After successful deployment:

- [ ] Test all demo queries
- [ ] Check logs for errors
- [ ] Monitor API usage
- [ ] Set up error tracking (optional)
- [ ] Share deployment URL
- [ ] Update README with live demo link

---

**Ready to deploy?** Follow [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions!
