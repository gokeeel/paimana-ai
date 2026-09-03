import { useEffect, useState } from "react";
import { Alert, Badge, Card, ListGroup, Spinner } from "react-bootstrap";
import { useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getProject, getProjectHistory, getProjectReasons } from "../api";

const STATUS_VARIANT = { "On Track": "success", "Needs Attention": "warning", Critical: "danger" };

export default function ProjectDetail() {
  const { uid } = useParams();
  const [project, setProject] = useState(null);
  const [history, setHistory] = useState(null);
  const [reasons, setReasons] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getProject(uid), getProjectHistory(uid), getProjectReasons(uid)])
      .then(([p, h, r]) => {
        setProject(p);
        setHistory(h);
        setReasons(r);
      })
      .catch((e) => setError(e.message));
  }, [uid]);

  if (error) return <Alert variant="danger">{error}</Alert>;
  if (!project || !history || !reasons) return <Spinner animation="border" />;

  return (
    <div className="d-flex flex-column gap-3">
      <Card body>
        <div className="d-flex justify-content-between align-items-center">
          <div>
            <Card.Title>{project.project_name}</Card.Title>
            <div className="text-muted">{project.agency} — {project.ministry} — {project.state}</div>
          </div>
          <Badge bg={STATUS_VARIANT[project.status] || "secondary"}>{project.status}</Badge>
        </div>
        <div className="mt-2">Physical progress: {project.physical_progress?.toFixed(0)}%</div>
        <div>Cost: ₹{project.latest_cost} Cr (sanctioned ₹{project.original_cost} Cr)</div>
      </Card>

      <Card body>
        <Card.Title>Risk Trend ({history.trend})</Card.Title>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={history.points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="report_month" />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Line type="monotone" dataKey="risk_score" stroke="#0d6efd" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card body>
        <Card.Title>Why Flagged</Card.Title>
        <ListGroup variant="flush">
          {reasons.reasons.length === 0 && <ListGroup.Item>No specific drivers identified.</ListGroup.Item>}
          {reasons.reasons.map((r, i) => (
            <ListGroup.Item key={i}>{r}</ListGroup.Item>
          ))}
        </ListGroup>
      </Card>
    </div>
  );
}
