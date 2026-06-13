import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../../api";
import ForceGraph from "../../components/ForceGraph";

interface Exam {
  id: number;
  name: string;
  subject: string;
  status: string;
  key_released: boolean;
  blob_hash?: string;
  start_ts: string;
}
interface Center {
  id: number;
  name: string;
  city: string;
  session_state: string;
}

function sampleQuestions(subject: string, n: number) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const difficulty = i % 4 === 0 ? "hard" : i % 4 === 1 ? "easy" : "medium";
    out.push({
      text: `[${subject}] Q${i + 1}. Sample question ${i + 1} (difficulty: ${difficulty}).`,
      options: [`Option A-${i + 1}`, `Option B-${i + 1}`, `Option C-${i + 1}`, `Option D-${i + 1}`],
      correct_index: i % 4,
      section: subject,
      difficulty,
      avg_response_s: difficulty === "hard" ? 34 : difficulty === "easy" ? 12 : 25,
    });
  }
  return out;
}

export default function AdminPortal() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [toast, setToast] = useState("");
  const [report, setReport] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  // create form
  const [name, setName] = useState("NEET-UG 2026 — Chemistry");
  const [subject, setSubject] = useState("Chemistry");
  const [minutes, setMinutes] = useState(2);
  const [sel, setSel] = useState<number[]>([]);

  function flash(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 3500);
  }

  async function refresh() {
    setExams(await apiGet("/exams"));
    setCenters(await apiGet("/centers"));
    setStats(await apiGet("/audit/stats"));
  }
  useEffect(() => {
    refresh().catch((e) => flash(e.message));
  }, []);

  async function createExam() {
    try {
      const start = new Date(Date.now() + minutes * 60000).toISOString();
      const exam = await apiPost("/exams", {
        name,
        subject,
        start_ts: start,
        duration_min: 180,
        center_ids: sel.length ? sel : centers.map((c) => c.id),
      });
      await apiPost(`/exams/${exam.id}/paper`, { questions: sampleQuestions(subject, 15) });
      flash(`Exam #${exam.id} created + paper encrypted (AES-256-GCM).`);
      refresh();
    } catch (e: any) {
      flash(e.message);
    }
  }

  async function distribute(id: number) {
    try {
      await apiPost(`/exams/${id}/distribute`);
      flash(`Paper distributed. PaperDistributed event written on-chain.`);
      refresh();
    } catch (e: any) {
      flash(e.message);
    }
  }

  async function runAnalysis(id: number) {
    setBusy(true);
    setReport(null);
    try {
      const r = await apiPost(`/fraud/${id}/analyze`);
      setReport(r);
      flash(`Analysis complete — ${r.flagged_count} candidates flagged. Logged on-chain.`);
      refresh();
    } catch (e: any) {
      flash(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-title">NTA Command Center</div>
      <div className="page-sub">
        Exam creation · encrypted paper distribution · live center status · fraud intelligence
      </div>

      <div className="stats">
        <div className="stat">
          <div className="n">{exams.length}</div>
          <div className="l">Exams</div>
        </div>
        <div className="stat">
          <div className="n">{centers.length}</div>
          <div className="l">Registered Centers</div>
        </div>
        <div className="stat">
          <div className="n">{stats?.total_events ?? "—"}</div>
          <div className="l">On-chain Events</div>
        </div>
        <div className="stat">
          <div className="n">{exams.filter((e) => e.key_released).length}</div>
          <div className="l">Keys Released</div>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>📝 Create Exam &amp; Encrypt Paper</h3>
          <div className="field">
            <label>Exam name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid grid-2" style={{ gap: 12 }}>
            <div className="field">
              <label>Subject</label>
              <input value={subject} onChange={(e) => setSubject(e.target.value)} />
            </div>
            <div className="field">
              <label>Starts in (min)</label>
              <input
                type="number"
                value={minutes}
                onChange={(e) => setMinutes(parseInt(e.target.value || "0"))}
              />
            </div>
          </div>
          <label>Assign centers</label>
          <div className="btn-row" style={{ marginBottom: 14 }}>
            {centers.map((c) => (
              <button
                key={c.id}
                className={`btn sm ${sel.includes(c.id) ? "primary" : ""}`}
                onClick={() =>
                  setSel((s) => (s.includes(c.id) ? s.filter((x) => x !== c.id) : [...s, c.id]))
                }
              >
                {c.city}
              </button>
            ))}
          </div>
          <button className="btn primary" onClick={createExam}>
            Create + encrypt 15-question paper
          </button>
          <p className="muted" style={{ marginTop: 10 }}>
            The paper is encrypted on upload; the plaintext is purged and the key is split
            between this server and the time-lock contract.
          </p>
        </div>

        <div className="card">
          <h3>
            🏛️ Exams <span className="sub">distribute → time-lock armed</span>
          </h3>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Exam</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {exams.map((e) => (
                <tr key={e.id}>
                  <td>{e.id}</td>
                  <td>
                    {e.name}
                    <br />
                    {e.blob_hash && (
                      <span className="hashstr">blob {e.blob_hash.slice(0, 18)}…</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${e.key_released ? "green" : "navy"}`}>{e.status}</span>
                  </td>
                  <td>
                    {e.status === "draft" || e.status === "distributed" ? (
                      <button className="btn sm" onClick={() => distribute(e.id)}>
                        Distribute
                      </button>
                    ) : (
                      <button className="btn sm" disabled={busy} onClick={() => runAnalysis(e.id)}>
                        Run Fraud Analysis
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>📡 Live Center Status</h3>
        <div className="grid grid-3">
          {centers.map((c) => (
            <div key={c.id} className="card" style={{ margin: 0 }}>
              <div className="row-between">
                <b style={{ fontSize: 14 }}>{c.city}</b>
                <span className={`tag-state s-${c.session_state}`}>{c.session_state}</span>
              </div>
              <p className="muted">{c.name}</p>
            </div>
          ))}
        </div>
      </div>

      {busy && (
        <div className="card">
          <span className="spinner" /> Running cross-submission statistical analysis…
        </div>
      )}

      {report && (
        <div className="card">
          <h3>🔍 IntegrityAI — Fraud Intelligence Report</h3>
          <p style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 16 }}>{report.summary}</p>
          <div className="stats" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
            <div className="stat">
              <div className="n">{report.submissions_analyzed}</div>
              <div className="l">Submissions</div>
            </div>
            <div className="stat">
              <div className="n">{report.flagged_count}</div>
              <div className="l">Flagged Candidates</div>
            </div>
            <div className="stat">
              <div className="n">{report.clusters.length}</div>
              <div className="l">Collusion Clusters</div>
            </div>
          </div>

          <h3 style={{ marginTop: 20 }}>Collusion Network Graph</h3>
          <ForceGraph nodes={report.graph.nodes} edges={report.graph.edges} />

          <h3 style={{ marginTop: 20 }}>Ranked Evidence</h3>
          <table>
            <thead>
              <tr>
                <th>Roll No</th>
                <th>Name</th>
                <th>Partners</th>
                <th>Score</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {report.ranked.map((r: any) => (
                <tr key={r.student_id}>
                  <td className="t-mono">{r.roll_no}</td>
                  <td>{r.name}</td>
                  <td>{r.partner_count}</td>
                  <td>
                    <span className="badge red">{(r.score * 100).toFixed(0)}%</span>
                  </td>
                  <td style={{ fontSize: 12 }}>{r.evidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
