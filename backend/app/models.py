"""SQLAlchemy ORM models — the schema source of truth for both the FastAPI
backend and the ml/ pipeline. Alembic migrations are generated from
Base.metadata here; never edit the database schema by hand."""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    uid = Column(String, primary_key=True)
    project_name = Column(String, nullable=False)
    agency = Column(String)
    ministry = Column(String)
    sector = Column(String)
    state = Column(String)
    original_cost = Column(Float)
    latest_cost = Column(Float)


class RiskScore(Base):
    __tablename__ = "risk_scores"

    uid = Column(String, ForeignKey("projects.uid"), primary_key=True)
    report_month = Column(String, nullable=False)
    physical_progress = Column(Float)
    slip_prob = Column(Float)
    cost_prob = Column(Float)
    risk_score = Column(Float, nullable=False)
    risk_tier = Column(String, nullable=False)
    alert_type = Column(String)
    risk_score_delta = Column(Float)


class RiskHistory(Base):
    __tablename__ = "risk_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String, ForeignKey("projects.uid"), nullable=False)
    report_month = Column(String, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_tier = Column(String, nullable=False)


class RiskDriver(Base):
    __tablename__ = "risk_drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String, ForeignKey("projects.uid"), nullable=False)
    report_month = Column(String, nullable=False)
    driver_rank = Column(Integer, nullable=False)
    feature = Column(String, nullable=False)
    shap_value = Column(Float, nullable=False)
    feature_value = Column(String)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="officer")
    ministry_scope = Column(String)


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dim = Column(String, nullable=False)
    dim_value = Column(String, nullable=False)
    report_month = Column(String, nullable=False)
    pct_on_budget = Column(Float)
    pct_on_time = Column(Float)
    n_projects = Column(Integer)


class ActionLog(Base):
    __tablename__ = "action_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String, ForeignKey("projects.uid"), nullable=False)
    officer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
