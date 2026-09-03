"""Single source of truth for the SQLAlchemy engine/session. Both the
FastAPI backend and the ml/ pipeline scripts import from here (via
ml/db.py) so there is exactly one place that knows how to connect."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

engine = create_engine(os.environ["DATABASE_URL"], future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
