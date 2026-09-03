from backend.app.models import Project, RiskDriver, RiskHistory, RiskScore


def _seed_project(db_session):
    db_session.add(Project(uid="1", project_name="Bridge A", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP",
                            original_cost=100.0, latest_cost=120.0))
    db_session.add(RiskScore(uid="1", report_month="2026-07", physical_progress=40.0,
                              risk_score=85.0, risk_tier="Red"))
    db_session.commit()


def test_get_project_status(client, db_session):
    _seed_project(db_session)
    resp = client.get("/api/projects/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "Critical"
    assert body["physical_progress"] == 40.0


def test_get_project_status_404_for_unknown_uid(client, db_session):
    resp = client.get("/api/projects/does-not-exist")
    assert resp.status_code == 404


def test_get_project_history_trend(client, db_session):
    _seed_project(db_session)
    db_session.add(RiskHistory(uid="1", report_month="2026-01", risk_score=20.0, risk_tier="Green"))
    db_session.add(RiskHistory(uid="1", report_month="2026-07", risk_score=85.0, risk_tier="Red"))
    db_session.commit()

    resp = client.get("/api/projects/1/history")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 2
    assert body["trend"] == "worsening"


def test_get_project_reasons(client, db_session):
    _seed_project(db_session)
    db_session.add(RiskDriver(uid="1", report_month="2026-07", driver_rank=1,
                               feature="elapsed_ratio", shap_value=9.0, feature_value="0.9"))
    db_session.add(RiskDriver(uid="1", report_month="2026-07", driver_rank=2,
                               feature="kw_bridge", shap_value=1.0, feature_value="1"))
    db_session.commit()

    resp = client.get("/api/projects/1/reasons")
    assert resp.status_code == 200
    body = resp.json()
    assert body["reasons"] == ["The project has used up 90% of its planned schedule."]
