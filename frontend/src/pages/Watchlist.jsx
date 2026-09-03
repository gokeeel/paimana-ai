import { useEffect, useState } from "react";
import { Alert, Badge, Card, Spinner } from "react-bootstrap";
import { Link } from "react-router-dom";
import { getWatchlist } from "../api";

const STATUS_VARIANT = { "On Track": "success", "Needs Attention": "warning", Critical: "danger" };

export default function Watchlist() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getWatchlist().then(setItems).catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert variant="danger">{error}</Alert>;
  if (!items) return <Spinner animation="border" />;

  return (
    <div className="d-flex flex-column gap-2">
      {items.map((item) => (
        <Card key={item.uid} body>
          <div className="d-flex justify-content-between align-items-start">
            <div>
              <Link to={`/projects/${item.uid}`}>{item.project_name}</Link>
              <div className="text-muted small">{item.agency} — {item.ministry}</div>
              {item.reason && <div className="mt-1">{item.reason}</div>}
            </div>
            <Badge bg={STATUS_VARIANT[item.status] || "secondary"}>{item.status}</Badge>
          </div>
        </Card>
      ))}
    </div>
  );
}
