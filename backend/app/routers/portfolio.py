from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=schemas.PortfolioSummary)
def get_summary(db: Session = Depends(get_db)):
    latest_month = db.query(func.max(models.RiskScore.report_month)).scalar() or ""
    q = db.query(models.RiskScore).filter(models.RiskScore.report_month == latest_month)
    total = q.count()
    needs_attention = q.filter(models.RiskScore.risk_tier.in_(["Amber", "Red"])).count()
    at_risk_cost = (
        db.query(func.coalesce(func.sum(models.Project.latest_cost), 0.0))
        .join(models.RiskScore, models.RiskScore.uid == models.Project.uid)
        .filter(models.RiskScore.report_month == latest_month, models.RiskScore.risk_tier == "Red")
        .scalar()
    )
    new_alerts = q.filter(models.RiskScore.alert_type.isnot(None)).count()
    return schemas.PortfolioSummary(
        total_projects=total,
        needs_attention=needs_attention,
        at_risk_cost=float(at_risk_cost or 0.0),
        new_alerts=new_alerts,
        report_month=latest_month,
    )
