"""Pytest configuration root-level conftest.py.

Ensures the repo root is in sys.path so that 'api' and 'scripts' imports work.
"""
import sys
from pathlib import Path

# Add repo root to sys.path
repo_root = Path(__file__).parent.resolve()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
