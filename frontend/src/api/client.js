import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export async function connectRepo({ source_type, source, branch }) {
  const body = { source_type, source };
  if (branch) {
    body.branch = branch;
  }
  const { data } = await api.post("/repo/connect", body);
  return data;
}

export async function startIndexing(repo_id) {
  const { data } = await api.post("/repo/index", { repo_id });
  return data;
}

export async function getJobStatus(job_id) {
  const { data } = await api.get(`/status/${job_id}`);
  return data;
}

export async function refreshRepo(repo_id) {
  const { data } = await api.post("/repo/refresh", { repo_id });
  return data;
}

export async function searchCommits({
  repo_id,
  query,
  top_k = 10,
  filters = null,
}) {
  const body = { repo_id, query, top_k };
  if (filters) {
    body.filters = filters;
  }
  const { data } = await api.post("/search", body);
  return data;
}

export async function getCommitDetail(sha, repo_id) {
  const { data } = await api.get(`/commit/${sha}`, {
    params: { repo_id },
  });
  return data;
}

export default api;
