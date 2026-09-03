from backend.app.models import Project, RiskDriver, RiskScore


def test_watchlist_returns_flagged_projects_with_a_reason(client, db_session):
    db_session.add(Project(uid="1", project_name="Bridge A", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP"))
    db_session.add(Project(uid="2", project_name="Bridge B", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP"))
    db_session.add(RiskScore(uid="1", report_month="2026-07", risk_score=85.0, risk_tier="Red"))
    db_session.add(RiskScore(uid="2", report_month="2026-07", risk_score=10.0, risk_tier="Green"))
    db_session.add(RiskDriver(uid="1", report_month="2026-07", driver_rank=1,
                               feature="elapsed_ratio", shap_value=9.0, feature_value="0.9"))
    db_session.commit()

    resp = client.get("/api/watchlist?tier=amber,red")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["uid"] == "1"
    assert body[0]["status"] == "Critical"
    assert body[0]["reason"] == "The project has used up 90% of its planned schedule."
