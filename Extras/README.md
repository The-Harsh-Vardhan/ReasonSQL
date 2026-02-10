# Extras - Development & Archive Files

This folder contains files that are not essential for deployment but may be useful for development, debugging, or understanding the project's evolution.

## 📁 Contents

### 🧪 Test Files
- `test_*.py` - Various test scripts for specific features
- `verify_*.py` - Verification scripts for bug fixes and updates

### 🐛 Debug & Development
- `debug_output.txt` - Debug logs
- `demo.py` - Original demo script (use `cli.py --demo` instead)
- `quickstart.py` - Early quickstart script
- `show_pipeline_doc.py` - Pipeline documentation generator

### 📝 Project Documentation & Summaries
- `BUGFIX_SUMMARY.md` - Summary of bug fixes
- `STATE_BUG_FIX_SUMMARY.md` - State consistency bug fix details
- `GEMINI_KEY_ROTATION_SUMMARY.py` - Gemini key rotation implementation notes
- `GEMINI_SWITCH_SUMMARY.py` - Gemini switch implementation notes
- `key_rotation_summary.py` - Key rotation summary
- `SETUP_SUMMARY.md` - Detailed setup summary (superseded by DEPLOYMENT.md)

### 📋 Problem Statement
- `Problem Statement/` - Original project problem statements and requirements

## 🎯 Purpose

These files are archived here to:
1. Keep the root directory clean and deployment-ready
2. Preserve development history and debugging artifacts
3. Maintain reference materials for future development
4. Document the evolution of the project

## 🚀 For Deployment

**You don't need this folder for deployment.** All essential files are in the root directory and core folders (agents/, orchestrator/, ui/, etc.).

## 🔍 When to Use These Files

- **Development:** Reference test files when adding new features
- **Debugging:** Check debug outputs and fix summaries for known issues
- **Learning:** Review problem statements and implementation notes
- **Testing:** Use test scripts to verify specific functionality

---

**Note:** This folder is automatically excluded from Docker builds via `.dockerignore`.
