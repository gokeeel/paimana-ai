import { useEffect, useState } from "react";
import { Alert, Card, Col, Row, Spinner } from "react-bootstrap";
import { getPortfolioSummary } from "../api";

export default function PortfolioHome() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getPortfolioSummary().then(setSummary).catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert variant="danger">{error}</Alert>;
  if (!summary) return <Spinner animation="border" />;

  const tiles = [
    ["Total Projects", summary.total_projects],
    ["Needs Attention", summary.needs_attention],
    ["₹ at Risk (Cr)", summary.at_risk_cost.toFixed(0)],
    ["New Alerts", summary.new_alerts],
  ];

  return (
    <Row className="g-3">
      {tiles.map(([label, value]) => (
        <Col md={3} key={label}>
          <Card body>
            <Card.Title>{label}</Card.Title>
            <h2>{value}</h2>
          </Card>
        </Col>
      ))}
    </Row>
  );
}
