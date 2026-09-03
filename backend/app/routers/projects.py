from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..templates import TIER_TO_STATUS, driver_to_sentence

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _latest_score(db, uid):
    return (
        db.query(models.RiskScore)
        .filter(models.RiskScore.uid == uid)
        .order_by(models.RiskScore.report_month.desc())
        .first()
    )


@router.get("/{uid}", response_model=schemas.ProjectStatus)
def get_project(uid: str, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.uid == uid).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    score = _latest_score(db, uid)
    if score is None:
        raise HTTPException(status_code=404, detail="No risk score for this project")
    return schemas.ProjectStatus(
        uid=project.uid,
        project_name=project.project_name,
        agency=project.agency or "",
        ministry=project.ministry or "",
        sector=project.sector or "",
        state=project.state or "",
        status=TIER_TO_STATUS.get(score.risk_tier, score.risk_tier),
        physical_progress=score.physical_progress,
        original_cost=project.original_cost,
        latest_cost=project.latest_cost,
        report_month=score.report_month,
    )


@router.get("/{uid}/history", response_model=schemas.ProjectHistory)
def get_project_history(uid: str, db: Session = Depends(get_db)):
    rows = (
        db.query(models.RiskHistory)
        .filter(models.RiskHistory.uid == uid)
        .order_by(models.RiskHistory.report_month)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No history for this project")
    points = [
        schemas.HistoryPoint(report_month=r.report_month, risk_score=r.risk_score, risk_tier=r.risk_tier)
        for r in rows
    ]
    if len(points) >= 2:
        delta = points[-1].risk_score - points[0].risk_score
        trend = "worsening" if delta > 5 else "improving" if delta < -5 else "stable"
    else:
        trend = "stable"
    return schemas.ProjectHistory(uid=uid, points=points, trend=trend)


@router.get("/{uid}/reasons", response_model=schemas.ProjectReasons)
def get_project_reasons(uid: str, db: Session = Depends(get_db)):
    latest_month = (
        db.query(func.max(models.RiskDriver.report_month))
        .filter(models.RiskDriver.uid == uid)
        .scalar()
    )
    drivers = (
        db.query(models.RiskDriver)
        .filter(models.RiskDriver.uid == uid, models.RiskDriver.report_month == latest_month)
        .order_by(models.RiskDriver.driver_rank)
        .all()
    )
    reasons = []
    for d in drivers:
        sentence = driver_to_sentence(d.feature, d.feature_value)
        if sentence:
            reasons.append(sentence)
        if len(reasons) == 3:
            break
    return schemas.ProjectReasons(uid=uid, reasons=reasons)
