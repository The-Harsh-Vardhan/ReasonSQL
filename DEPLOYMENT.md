# 🚀 Deployment Guide

This guide covers deploying the NL2SQL Multi-Agent System to various platforms.

## 📋 Table of Contents
- [Streamlit Cloud Deployment](#streamlit-cloud-deployment)
- [Local Deployment](#local-deployment)
- [Docker Deployment](#docker-deployment)
- [Environment Variables](#environment-variables)

---

## ☁️ Streamlit Cloud Deployment

### Prerequisites
- GitHub account
- Streamlit Cloud account (free at [streamlit.io/cloud](https://streamlit.io/cloud))
- API key from either:
  - Groq (recommended - free): https://console.groq.com/keys
  - Google Gemini: https://makersuite.google.com/app/apikey

### Step-by-Step Instructions

#### 1. Fork/Clone Repository
```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/nl2sql-multiagent.git
cd nl2sql-multiagent

# Push to your GitHub account
git remote set-url origin https://github.com/YOUR_USERNAME/nl2sql-multiagent.git
git push -u origin main
```

#### 2. Deploy on Streamlit Cloud

1. **Sign in to Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub

2. **Create New App**
   - Click "New app"
   - Select your repository: `YOUR_USERNAME/nl2sql-multiagent`
   - Main file path: `ui/streamlit_app.py`
   - App URL: Choose your custom URL

3. **Configure Secrets**
   - Click on "Advanced settings" → "Secrets"
   - Copy content from `.streamlit/secrets.toml.example`
   - Paste and update with your actual API keys:

   ```toml
   [api_keys]
   GROQ_API_KEY = "gsk_your_actual_groq_key"
   GOOGLE_API_KEY = "your_actual_google_key"
   LLM_PROVIDER = "gemini"
   LLM_MODEL = "gemini/gemini-pro"
   DATABASE_PATH = "data/chinook.db"
   ```

4. **Deploy**
   - Click "Deploy!"
   - Wait 2-3 minutes for deployment
   - Your app will be live at: `https://your-app-name.streamlit.app`

#### 3. Update Configuration (if needed)

The app will automatically:
- Install dependencies from `requirements.txt`
- Use the included `data/chinook.db` database
- Load secrets from Streamlit Cloud secrets management

---

## 💻 Local Deployment

### Quick Start

```bash
# 1. Clone repository
git clone https://github.com/YOUR_USERNAME/nl2sql-multiagent.git
cd nl2sql-multiagent

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your API keys

# 5. Run setup (downloads database if needed)
python setup.py

# 6. Launch Streamlit app
streamlit run ui/streamlit_app.py
```

The app will open at `http://localhost:8501`

### CLI Usage

```bash
# Interactive mode
python cli.py

# Demo mode (5 preset queries)
python cli.py --demo

# Single query
python cli.py -q "How many customers are from Brazil?"

# Verbose mode (full agent trace)
python cli.py --verbose

# Full mode (all 12 agents)
python cli.py --full
```

---

## 🐳 Docker Deployment

### Build and Run

```bash
# Build image
docker build -t nl2sql-multiagent .

# Run container
docker run -p 8501:8501 \
  -e GROQ_API_KEY=your_key \
  -e LLM_PROVIDER=groq \
  nl2sql-multiagent
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - LLM_PROVIDER=gemini
    volumes:
      - ./data:/app/data
```

Run with:
```bash
docker-compose up
```

---

## 🔑 Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | `gsk_abc123...` |
| `GOOGLE_API_KEY` | Google Gemini API key | `AIzaSy...` |
| `LLM_PROVIDER` | Which LLM to use | `groq` or `gemini` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `gemini/gemini-pro` | Model name |
| `DATABASE_PATH` | `data/chinook.db` | Path to SQLite database |
| `MAX_RETRIES` | `3` | Max SQL retry attempts |

### For Streamlit Cloud

Add these in the Streamlit Cloud dashboard under **Settings → Secrets**:

```toml
[api_keys]
GROQ_API_KEY = "your_key_here"
GOOGLE_API_KEY = "your_key_here"
LLM_PROVIDER = "gemini"
LLM_MODEL = "gemini/gemini-pro"
DATABASE_PATH = "data/chinook.db"
```

### For Local Development

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
GROQ_API_KEY=gsk_your_actual_key
GOOGLE_API_KEY=your_actual_key
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-pro
DATABASE_PATH=data/chinook.db
```

---

## 🔍 Troubleshooting

### Common Issues

#### 1. API Key Not Working
**Error:** `ConfigurationError: GROQ_API_KEY is not configured`

**Solution:**
- Verify API key is correctly set in secrets/environment
- Check for extra spaces or quotes
- Ensure key is active (not expired)

#### 2. Database Not Found
**Error:** `Database file not found: data/chinook.db`

**Solution:**
```bash
python setup.py  # This downloads the database
```

#### 3. Module Import Errors
**Error:** `ModuleNotFoundError: No module named 'crewai'`

**Solution:**
```bash
pip install -r requirements.txt
```

#### 4. Rate Limit Exceeded
**Error:** `Rate limit exceeded`

**Solution:**
- Wait 60 seconds and retry
- Switch to different LLM provider in settings
- Add multiple API keys for rotation

---

## 📊 Performance Optimization

### For Production Deployment

1. **Use Multiple API Keys**
   - Configure key rotation in config/settings.py
   - Add 3-4 keys for better throughput

2. **Database Optimization**
   - Use indexes on frequently queried columns
   - Enable WAL mode for SQLite
   - Consider PostgreSQL for production

3. **Caching**
   - Enable Streamlit caching for schema queries
   - Cache agent responses for common queries

4. **Monitoring**
   - Set up logging to track errors
   - Monitor API quota usage
   - Track response times

---

## 🛡️ Security Best Practices

1. **Never commit API keys**
   - Use `.env` for local development
   - Use secrets management for cloud deployment
   - Rotate keys regularly

2. **Database Security**
   - Use read-only database connections
   - Validate all SQL queries before execution
   - Implement query timeouts

3. **Rate Limiting**
   - Implement user-level rate limiting
   - Use API key rotation
   - Monitor for abuse

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/YOUR_USERNAME/nl2sql-multiagent/issues)
- **Documentation:** [Project README](../README.md)
- **License:** MIT

---

**Ready to Deploy?** Follow the [Streamlit Cloud](#streamlit-cloud-deployment) section above!
