import { Container, Nav, Navbar } from "react-bootstrap";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import PortfolioHome from "./pages/PortfolioHome";
import ProjectDetail from "./pages/ProjectDetail";
import Watchlist from "./pages/Watchlist";

export default function App() {
  return (
    <BrowserRouter>
      <Navbar bg="dark" variant="dark">
        <Container>
          <Navbar.Brand as={Link} to="/">PAIMANA-AI</Navbar.Brand>
          <Nav>
            <Nav.Link as={Link} to="/">Portfolio</Nav.Link>
            <Nav.Link as={Link} to="/watchlist">Watchlist</Nav.Link>
          </Nav>
        </Container>
      </Navbar>
      <Container className="mt-4">
        <Routes>
          <Route path="/" element={<PortfolioHome />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/projects/:uid" element={<ProjectDetail />} />
        </Routes>
      </Container>
    </BrowserRouter>
  );
}
