# Contributing to NL2SQL Multi-Agent System

Thank you for your interest in contributing! This document provides guidelines and best practices.

## 🚀 Getting Started

1. **Fork the repository** and clone your fork
2. **Set up the environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
3. **Configure API key** (see `.env.example`)
4. **Run tests** to make sure everything works:
   ```bash
   python demo.py
   ```

## 📁 Project Structure

```
nl2sql_system/
├── agents/           # Agent definitions (12 specialized agents)
├── config/           # Configuration and settings
├── models/           # Pydantic models for data flow
├── orchestrator/     # State-machine orchestrator (main logic)
├── tasks/            # CrewAI task definitions
├── tools/            # Custom database tools
├── ui/               # Streamlit web interface
├── examples/         # Example reasoning traces
└── data/             # Database files (not tracked in git)
```

## 🔧 Development Guidelines

### Code Style

- **Python 3.10+** features are welcome
- Use **type hints** for function signatures
- Follow **PEP 8** style guidelines
- Add **docstrings** to all public functions

### Commit Messages

Use clear, descriptive commit messages:
```
feat: Add new QueryOptimizer agent
fix: Handle empty result sets in ResultValidator
docs: Update README with new architecture diagram
refactor: Simplify orchestrator state transitions
```

### Adding New Agents

1. Define the agent in `agents/agent_definitions.py`
2. Add output model in `models/agent_outputs.py`
3. Add step in `orchestrator/deterministic_orchestrator.py`
4. Update the README architecture diagram

### Safety First

This project handles database queries. When contributing:

- **Never remove safety checks** (FORBIDDEN_KEYWORDS, LIMIT enforcement)
- **Test with edge cases** (SQL injection attempts, malformed queries)
- **Validate all user inputs** before processing

## 🐛 Reporting Issues

When reporting issues, please include:

1. **Environment**: Python version, OS, dependencies
2. **Steps to reproduce**: Minimal code/commands to trigger the issue
3. **Expected vs actual behavior**
4. **Error messages**: Full stack trace if applicable

## 💡 Feature Requests

We welcome feature ideas! Please:

1. Check if the feature is already requested
2. Describe the use case and benefits
3. Consider backward compatibility

## 📝 Pull Request Process

1. **Create a feature branch**: `git checkout -b feat/my-feature`
2. **Make your changes** with clear commits
3. **Update documentation** if needed
4. **Run the demo** to verify nothing is broken
5. **Submit PR** with a clear description

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] New features include documentation
- [ ] Safety constraints are preserved
- [ ] Demo runs successfully

## 🏆 Recognition

Contributors will be acknowledged in the README!

---

Thank you for helping make NL2SQL better! 🙏
