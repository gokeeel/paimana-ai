from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..templates import TIER_TO_STATUS, driver_to_sentence

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[schemas.WatchlistItem])
def get_watchlist(tier: str = Query("amber,red"), db: Session = Depends(get_db)):
    tiers = [t.strip().capitalize() for t in tier.split(",")]
    latest_month = db.query(func.max(models.RiskScore.report_month)).scalar() or ""
    rows = (
        db.query(models.RiskScore, models.Project)
        .join(models.Project, models.Project.uid == models.RiskScore.uid)
        .filter(models.RiskScore.report_month == latest_month, models.RiskScore.risk_tier.in_(tiers))
        .order_by(models.RiskScore.risk_score.desc())
        .all()
    )
    items = []
    for score, project in rows:
        driver = (
            db.query(models.RiskDriver)
            .filter(models.RiskDriver.uid == project.uid, models.RiskDriver.report_month == latest_month)
            .order_by(models.RiskDriver.driver_rank)
            .first()
        )
        reason = driver_to_sentence(driver.feature, driver.feature_value) if driver else None
        items.append(schemas.WatchlistItem(
            uid=project.uid,
            project_name=project.project_name,
            agency=project.agency or "",
            ministry=project.ministry or "",
            status=TIER_TO_STATUS.get(score.risk_tier, score.risk_tier),
            reason=reason,
        ))
    return items
