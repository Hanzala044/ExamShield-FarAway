import { useEffect, useState } from "react";
import { apiGet } from "../../api";

const TYPE_COLOR: Record<string, string> = {
  PaperDistributed: "navy",
  CenterVerified: "blue",
  StudentCheckedIn: "green",
  KeyReleased: "red",
  SessionOpened: "green",
  SessionClosed: "navy",
  AnomalyFlagged: "red",
  AnalysisComplete: "purple",
};

export default function AuditTrail() {
  const [events, setEvents] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [integrity, setIntegrity] = useState<any>(null);
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<any>(null);

  async function load() {
    setEvents(await apiGet("/audit/events" + (filter ? `?event_type=${filter}` : "")));
    setStats(await apiGet("/audit/stats"));
    setIntegrity(await apiGet("/audit/chain-integrity"));
  }
  useEffect(() => {
    load().catch(() => {});
  }, [filter]);

  async function verify() {
    if (!query) return;
    setResult(await apiGet(`/audit/verify?hash=${encodeURIComponent(query)}`));
  }

  return (
    <>
      <div className="page-title">Public Audit Trail</div>
      <div className="page-sub">
        Immutable, hash-chained event ledger — verifiable by any citizen, no login required.
      </div>

      <div className="stats">
        <div className="stat">
          <div className="n">{stats?.total_events ?? "—"}</div>
          <div className="l">Total Events</div>
        </div>
        <div className="stat">
          <div className="n" style={{ color: integrity?.valid ? "var(--green)" : "var(--red)" }}>
            {integrity ? (integrity.valid ? "VALID" : "BROKEN") : "—"}
          </div>
          <div className="l">Chain Integrity</div>
        </div>
        <div className="stat">
          <div className="n">{stats?.by_type?.AnomalyFlagged ?? 0}</div>
          <div className="l">Anomalies Logged</div>
        </div>
        <div className="stat">
          <div className="n">{stats?.simulated ? "SIM" : "LIVE"}</div>
          <div className="l">Polygon Mode</div>
        </div>
      </div>

      <div className="card">
        <h3>🔎 Verify an Event Hash</h3>
        <div className="flex">
          <input
            placeholder="Paste a payload hash or tx hash from any record below"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="btn primary" onClick={verify}>
            Verify
          </button>
        </div>
        {result && (
          <div className="alert" style={{ marginTop: 12, borderColor: result.found ? "var(--green-b)" : "var(--red-b)", background: result.found ? "var(--green-s)" : "var(--red-s)" }}>
            {result.found ? (
              <div className="note">
                ✅ Verified — <b>{result.event_type}</b> in block #{result.block_number} at{" "}
                {result.ts}.
              </div>
            ) : (
              <div className="note">❌ No event found for that hash.</div>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h3>
          ⛓️ Ledger
          <span className="sub">most recent first</span>
        </h3>
        <div className="btn-row" style={{ marginBottom: 14 }}>
          <button className={`btn sm ${filter === "" ? "primary" : ""}`} onClick={() => setFilter("")}>
            All
          </button>
          {Object.keys(TYPE_COLOR).map((t) => (
            <button
              key={t}
              className={`btn sm ${filter === t ? "primary" : ""}`}
              onClick={() => setFilter(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <table>
          <thead>
            <tr>
              <th>Block</th>
              <th>Event</th>
              <th>Tx / Payload Hash</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.tx_hash}>
                <td className="t-mono">#{e.block_number}</td>
                <td>
                  <span className={`badge ${TYPE_COLOR[e.event_type] || ""}`}>{e.event_type}</span>
                </td>
                <td>
                  <div className="hashstr">{e.tx_hash}</div>
                  <div className="hashstr" style={{ opacity: 0.6 }}>
                    payload {e.payload_hash.slice(0, 24)}…
                  </div>
                </td>
                <td className="t-mono">{new Date(e.ts).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length === 0 && <div className="empty">No events yet.</div>}
      </div>
    </>
  );
}
