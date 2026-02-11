"""
Conftest for ReasonSQL tests.

Ensures project root and backend directory are on sys.path
so that 'backend', 'configs', and legacy bare imports resolve correctly.
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add backend/ directory for legacy bare imports used in orchestrator modules
backend_dir = str(Path(__file__).parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
