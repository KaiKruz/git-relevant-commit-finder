import { useEffect, useMemo, useRef, useState } from "react";
import {
  connectRepo,
  getCommitDetail,
  getJobStatus,
  refreshRepo,
  searchCommits,
  startIndexing,
} from "./api/client";

function toErrorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.error ||
    error?.message ||
    "Something went wrong"
  );
}

function buildFilters(filters) {
  const payload = {};

  if (filters.author.trim()) payload.author = filters.author.trim();
  if (filters.from_date) payload.from_date = filters.from_date;
  if (filters.to_date) payload.to_date = filters.to_date;
  if (filters.path_contains.trim()) payload.path_contains = filters.path_contains.trim();
  if (filters.branch.trim()) payload.branch = filters.branch.trim();

  return Object.keys(payload).length > 0 ? payload : null;
}

export default function App() {
  const [sourceType, setSourceType] = useState("github");
  const [source, setSource] = useState("");
  const [branch, setBranch] = useState("main");

  const [repo, setRepo] = useState(null);
  const [status, setStatus] = useState(null);

  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({
    author: "",
    from_date: "",
    to_date: "",
    path_contains: "",
    branch: "",
  });

  const [results, setResults] = useState([]);
  const [selectedSha, setSelectedSha] = useState("");
  const [commitDetail, setCommitDetail] = useState(null);

  const [connectLoading, setConnectLoading] = useState(false);
  const [jobLoading, setJobLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  const [connectError, setConnectError] = useState("");
  const [jobError, setJobError] = useState("");
  const [searchError, setSearchError] = useState("");
  const [detailError, setDetailError] = useState("");

  const pollTimeoutRef = useRef(null);

  const repoId = repo?.repo_id || "";

  const statusText = useMemo(() => {
    if (!status) return "idle";
    const progress = typeof status.progress === "number" ? ` (${status.progress}%)` : "";
    return `${status.status || "unknown"}${progress}`;
  }, [status]);

  function clearPolling() {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }

  function startPolling(jobId) {
    clearPolling();

    const tick = async () => {
      try {
        const current = await getJobStatus(jobId);
        setStatus(current);
        setJobError("");

        if (current.status === "completed" || current.status === "failed") {
          setJobLoading(false);
          return;
        }

        pollTimeoutRef.current = setTimeout(tick, 1200);
      } catch (error) {
        setJobLoading(false);
        setJobError(toErrorMessage(error));
      }
    };

    pollTimeoutRef.current = setTimeout(tick, 0);
  }

  useEffect(() => {
    return () => {
      clearPolling();
    };
  }, []);

  async function onConnect(event) {
    event.preventDefault();

    setConnectLoading(true);
    setConnectError("");

    try {
      const connected = await connectRepo({
        source_type: sourceType,
        source: source.trim(),
        branch: branch.trim() || null,
      });

      setRepo(connected);
      setStatus({
        job_id: "-",
        status: connected.status || "connected",
        progress: 0,
        message: "Repository connected",
        stats: {
          indexed_commits: 0,
          new_embeddings: 0,
          total_commits: 0,
        },
        error: null,
      });
      setResults([]);
      setSelectedSha("");
      setCommitDetail(null);
      setSearchError("");
      setDetailError("");
    } catch (error) {
      setConnectError(toErrorMessage(error));
    } finally {
      setConnectLoading(false);
    }
  }

  async function runJob(jobType) {
    if (!repoId) return;

    setJobLoading(true);
    setJobError("");

    try {
      const queued =
        jobType === "refresh" ? await refreshRepo(repoId) : await startIndexing(repoId);

      setStatus({
        job_id: queued.job_id,
        status: queued.status,
        progress: 0,
        message: `${jobType} queued`,
        stats: {
          indexed_commits: 0,
          new_embeddings: 0,
          total_commits: 0,
        },
        error: null,
      });
      startPolling(queued.job_id);
    } catch (error) {
      setJobLoading(false);
      setJobError(toErrorMessage(error));
    }
  }

  async function onSearch(event) {
    event.preventDefault();
    if (!repoId) return;
    if (!query.trim()) {
      setSearchError("Enter a search query.");
      return;
    }

    setSearchLoading(true);
    setSearchError("");

    try {
      const response = await searchCommits({
        repo_id: repoId,
        query: query.trim(),
        top_k: 10,
        filters: buildFilters(filters),
      });
      setResults(response.results || []);
      setSelectedSha("");
      setCommitDetail(null);
      setDetailError("");
    } catch (error) {
      setResults([]);
      setSearchError(toErrorMessage(error));
    } finally {
      setSearchLoading(false);
    }
  }

  async function onSelectResult(sha) {
    if (!repoId) return;

    setSelectedSha(sha);
    setDetailLoading(true);
    setDetailError("");

    try {
      const detail = await getCommitDetail(sha, repoId);
      setCommitDetail(detail);
    } catch (error) {
      setCommitDetail(null);
      setDetailError(toErrorMessage(error));
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <h1>Git Relevant Commit Finder</h1>

      <section className="panel">
        <h2>Repository</h2>
        <form onSubmit={onConnect} className="form-grid">
          <label>
            Source Type
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
              <option value="github">github</option>
              <option value="local">local</option>
            </select>
          </label>

          <label>
            Source
            <input
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="https://github.com/org/repo.git or C:/path/to/repo"
              required
            />
          </label>

          <label>
            Branch
            <input
              value={branch}
              onChange={(event) => setBranch(event.target.value)}
              placeholder="main"
            />
          </label>

          <div className="button-row">
            <button type="submit" disabled={connectLoading || !source.trim()}>
              {connectLoading ? "Connecting..." : "Connect"}
            </button>
            <button
              type="button"
              onClick={() => runJob("index")}
              disabled={!repoId || jobLoading}
            >
              {jobLoading ? "Working..." : "Index"}
            </button>
            <button
              type="button"
              onClick={() => runJob("refresh")}
              disabled={!repoId || jobLoading}
            >
              {jobLoading ? "Working..." : "Refresh"}
            </button>
          </div>
        </form>

        <div className="status-box">
          <strong>Status:</strong> {statusText}
          <div>repo_id: {repoId || "-"}</div>
          <div>job_id: {status?.job_id || "-"}</div>
          <div>message: {status?.message || "-"}</div>
          <div>
            stats: {status?.stats?.indexed_commits || 0} indexed, {status?.stats?.new_embeddings || 0} new
          </div>
          {status?.error ? <p className="error">status error: {status.error}</p> : null}
          {connectError ? <p className="error">connect error: {connectError}</p> : null}
          {jobError ? <p className="error">job error: {jobError}</p> : null}
        </div>
      </section>

      <section className="panel">
        <h2>Search</h2>
        <form onSubmit={onSearch} className="form-grid">
          <label>
            Query
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="when was auth refactored?"
            />
          </label>

          <label>
            author
            <input
              value={filters.author}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  author: event.target.value,
                }))
              }
            />
          </label>

          <label>
            from_date
            <input
              type="date"
              value={filters.from_date}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  from_date: event.target.value,
                }))
              }
            />
          </label>

          <label>
            to_date
            <input
              type="date"
              value={filters.to_date}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  to_date: event.target.value,
                }))
              }
            />
          </label>

          <label>
            path_contains
            <input
              value={filters.path_contains}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  path_contains: event.target.value,
                }))
              }
            />
          </label>

          <label>
            branch
            <input
              value={filters.branch}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  branch: event.target.value,
                }))
              }
            />
          </label>

          <div className="button-row">
            <button type="submit" disabled={!repoId || searchLoading}>
              {searchLoading ? "Searching..." : "Search"}
            </button>
          </div>
        </form>
        {searchError ? <p className="error">search error: {searchError}</p> : null}
      </section>

      <section className="content-grid">
        <div className="panel">
          <h2>Results</h2>
          {searchLoading ? <p>Loading results...</p> : null}
          {!searchLoading && results.length === 0 ? <p>Empty results.</p> : null}

          <ul className="results-list">
            {results.map((item) => (
              <li key={item.sha}>
                <button
                  type="button"
                  className={`result-item ${selectedSha === item.sha ? "active" : ""}`}
                  onClick={() => onSelectResult(item.sha)}
                >
                  <div className="result-title">
                    #{item.rank} {item.message}
                  </div>
                  <div className="result-meta">
                    {item.short_sha} | {item.author_name} | {item.date}
                  </div>
                  <div className="result-meta">
                    score {Number(item.rerank_score).toFixed(3)} | +{item.additions} / -{item.deletions}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel">
          <h2>Commit Detail</h2>
          {detailLoading ? <p>Loading commit detail...</p> : null}
          {detailError ? <p className="error">detail error: {detailError}</p> : null}
          {!detailLoading && !detailError && !commitDetail ? <p>Select a result to view detail.</p> : null}

          {commitDetail ? (
            <div className="detail-box">
              <p>
                <strong>message:</strong> {commitDetail.message}
              </p>
              <p>
                <strong>sha:</strong> {commitDetail.sha}
              </p>
              <p>
                <strong>author:</strong> {commitDetail.author_name} ({commitDetail.author_email})
              </p>
              <p>
                <strong>date:</strong> {commitDetail.date}
              </p>
              <p>
                <strong>files:</strong> {commitDetail.files?.length || 0}
              </p>
              {commitDetail.files?.length ? (
                <ul className="file-list">
                  {commitDetail.files.map((file) => (
                    <li key={file}>{file}</li>
                  ))}
                </ul>
              ) : null}
              <p>
                <strong>additions/deletions:</strong> +{commitDetail.additions} / -{commitDetail.deletions}
              </p>
              <p>
                <strong>github:</strong>{" "}
                {commitDetail.github_url ? (
                  <a href={commitDetail.github_url} target="_blank" rel="noreferrer">
                    open commit
                  </a>
                ) : (
                  "not available"
                )}
              </p>
              <p>
                <strong>diff preview:</strong>
              </p>
              <pre>{commitDetail.diff_preview || "No preview"}</pre>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
