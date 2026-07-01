from __future__ import annotations

from pathlib import Path

# Backend/paths.py lives in <repo>/Backend.
REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "Frontend"

STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
