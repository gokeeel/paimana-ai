from backend.app.models import Project, RiskScore


def test_portfolio_summary(client, db_session):
    db_session.add(Project(uid="1", project_name="Bridge A", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP",
                            original_cost=100.0, latest_cost=120.0))
    db_session.add(Project(uid="2", project_name="Bridge B", agency="NHAI",
                            ministry="MoRTH", sector="Roads", state="UP",
                            original_cost=200.0, latest_cost=200.0))
    db_session.add(RiskScore(uid="1", report_month="2026-07", risk_score=85.0,
                              risk_tier="Red", alert_type="Rapidly Deteriorating"))
    db_session.add(RiskScore(uid="2", report_month="2026-07", risk_score=10.0,
                              risk_tier="Green", alert_type=None))
    db_session.commit()

    resp = client.get("/api/portfolio/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_projects"] == 2
    assert body["needs_attention"] == 1
    assert body["at_risk_cost"] == 120.0
    assert body["new_alerts"] == 1
    assert body["report_month"] == "2026-07"
