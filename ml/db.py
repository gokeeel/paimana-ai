"""Thin re-export so ml/ pipeline scripts share the exact same engine and
schema as the FastAPI backend — backend/app/database.py and
backend/app/models.py are the single source of truth, this just makes them
importable from scripts run as `python ml/score_projects.py`."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import SessionLocal, engine  # noqa: E402,F401
from backend.app.models import Base  # noqa: E402,F401
