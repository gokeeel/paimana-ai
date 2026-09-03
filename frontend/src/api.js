const BASE_URL = "http://localhost:8000/api";

async function getJSON(path) {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`Request to ${path} failed (${res.status})`);
  return res.json();
}

export const getPortfolioSummary = () => getJSON("/portfolio/summary");
export const getWatchlist = (tier = "amber,red") => getJSON(`/watchlist?tier=${tier}`);
export const getProject = (uid) => getJSON(`/projects/${uid}`);
export const getProjectHistory = (uid) => getJSON(`/projects/${uid}/history`);
export const getProjectReasons = (uid) => getJSON(`/projects/${uid}/reasons`);
