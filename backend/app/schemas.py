from typing import Optional

from pydantic import BaseModel


class PortfolioSummary(BaseModel):
    total_projects: int
    needs_attention: int
    at_risk_cost: float
    new_alerts: int
    report_month: str


class WatchlistItem(BaseModel):
    uid: str
    project_name: str
    agency: str
    ministry: str
    status: str
    reason: Optional[str] = None


class ProjectStatus(BaseModel):
    uid: str
    project_name: str
    agency: str
    ministry: str
    sector: str
    state: str
    status: str
    physical_progress: Optional[float]
    original_cost: Optional[float]
    latest_cost: Optional[float]
    report_month: str


class HistoryPoint(BaseModel):
    report_month: str
    risk_score: float
    risk_tier: str


class ProjectHistory(BaseModel):
    uid: str
    points: list[HistoryPoint]
    trend: str


class ProjectReasons(BaseModel):
    uid: str
    reasons: list[str]
