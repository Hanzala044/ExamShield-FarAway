import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost, wsUrl } from "../../api";
import { useAuth } from "../../auth";

interface Center {
  id: number;
  name: string;
  city: string;
  lat: number;
  lon: number;
  session_state: string;
}
interface Exam {
  id: number;
  name: string;
  status: string;
  key_released: boolean;
  start_ts: string;
}
interface Student {
  id: number;
  roll_no: string;
  name: string;
  seat: string;
  checked_in: boolean;
  match_score: number | null;
  override: boolean;
}

export default function CenterDashboard() {
  const { session } = useAuth();
  const [centers, setCenters] = useState<Center[]>([]);
  const [centerId, setCenterId] = useState<number | null>(session?.center_id ?? null);
  const [center, setCenter] = useState<Center | null>(null);
  const [exams, setExams] = useState<Exam[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [toast, setToast] = useState("");
  const [roll, setRoll] = useState("");
  const [mismatch, setMismatch] = useState<any>(null);
  const [reason, setReason] = useState("Verified against physical photo ID");
  const ws = useRef<WebSocket | null>(null);

  function flash(m: string) {
    setToast(m);
    setTimeout(() => setToast(""), 3500);
  }

  const liveExam = exams.find((e) => e.status === "active" || e.status === "distributed");

  async function loadCenters() {
    const cs = await apiGet("/centers");
    setCenters(cs);
    if (centerId == null && cs.length) setCenterId(cs[0].id);
  }

  async function loadCenter(id: number) {
    setCenter(await apiGet(`/centers/${id}`));
    setExams(await apiGet(`/centers/${id}/exams`));
    setStudents(await apiGet(`/centers/${id}/students`));
  }

  useEffect(() => {
    loadCenters().catch((e) => flash(e.message));
  }, []);

  useEffect(() => {
    if (centerId == null) return;
    loadCenter(centerId).catch((e) => flash(e.message));
    ws.current?.close();
    const sock = new WebSocket(wsUrl(`/ws/center/${centerId}`));
    sock.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "anomaly") setAlerts((a) => [msg, ...a].slice(0, 50));
      if (msg.type === "session_opened") flash(msg.message);
    };
    ws.current = sock;
    return () => sock.close();
  }, [centerId]);

  async function checkin() {
    if (!centerId || !roll) return;
    setMismatch(null);
    try {
      const r = await apiPost(`/centers/${centerId}/checkin`, { roll_no: roll });
      if (r.status === "checked_in") {
        flash(`${r.name} checked in (match ${(r.score * 100).toFixed(0)}%). Seat ${r.seat}.`);
        setRoll("");
        loadCenter(centerId);
      } else {
        setMismatch(r);
      }
    } catch (e: any) {
      flash(e.message);
    }
  }

  async function decideOverride(approve: boolean) {
    if (!centerId || !mismatch) return;
    try {
      await apiPost(`/centers/${centerId}/override`, {
        student_id: mismatch.student_id,
        approve,
        reason,
      });
      flash(approve ? "Override approved — logged on-chain." : "Entry denied — logged on-chain.");
      setMismatch(null);
      setRoll("");
      loadCenter(centerId);
    } catch (e: any) {
      flash(e.message);
    }
  }

  async function releaseKey() {
    if (!center || !liveExam) return;
    try {
      const r = await apiPost("/centers/release-key", {
        exam_id: liveExam.id,
        center_id: center.id,
        device_lat: center.lat,
        device_lon: center.lon,
      });
      flash(`Key released (device ${r.geofence_distance_m}m from center). Exam is live.`);
      loadCenter(center.id);
    } catch (e: any) {
      flash(e.message);
    }
  }

  async function closeSession() {
    if (!center || !liveExam) return;
    try {
      const r = await apiPost(`/centers/close-session?exam_id=${liveExam.id}&center_id=${center.id}`);
      flash(`Session locked. ${r.submission_count} submissions checksummed on-chain.`);
      loadCenter(center.id);
    } catch (e: any) {
      flash(e.message);
    }
  }

  const checkedIn = students.filter((s) => s.checked_in).length;

  return (
    <>
      <div className="row-between">
        <div>
          <div className="page-title">Center Console</div>
          <div className="page-sub">
            {center ? `${center.name} · ${center.city}` : "Loading…"}
          </div>
        </div>
        {session?.role === "super_admin" && (
          <select
            style={{ width: 240 }}
            value={centerId ?? ""}
            onChange={(e) => setCenterId(parseInt(e.target.value))}
          >
            {centers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.city} — {c.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="stats">
        <div className="stat">
          <div className="n">{students.length}</div>
          <div className="l">Students</div>
        </div>
        <div className="stat">
          <div className="n">{checkedIn}</div>
          <div className="l">Checked In</div>
        </div>
        <div className="stat">
          <div className="n">{alerts.length}</div>
          <div className="l">Live Anomalies</div>
        </div>
        <div className="stat">
          <div className="n" style={{ textTransform: "capitalize" }}>
            {center?.session_state ?? "—"}
          </div>
          <div className="l">Session State</div>
        </div>
      </div>

      <div className="card">
        <h3>
          ⏱️ Session Control
          {liveExam && <span className="sub">{liveExam.name}</span>}
        </h3>
        {liveExam ? (
          <div className="btn-row">
            <button className="btn green" disabled={liveExam.key_released} onClick={releaseKey}>
              {liveExam.key_released ? "Key Released ✓" : "Release Time-Locked Key"}
            </button>
            <button className="btn danger" onClick={closeSession}>
              Close &amp; Lock Session
            </button>
            <span className="muted">
              Time-lock + GPS geofence are enforced server-side before the key is released.
            </span>
          </div>
        ) : (
          <p className="muted">No live exam assigned to this center.</p>
        )}
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>🪪 VerifyGate — Student Check-In</h3>
          <div className="flex">
            <input
              placeholder="Scan QR / enter roll no (e.g. NEET2026-0001)"
              value={roll}
              onChange={(e) => setRoll(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && checkin()}
            />
            <button className="btn primary" onClick={checkin}>
              Verify Face
            </button>
          </div>

          {mismatch && (
            <div className="alert" style={{ marginTop: 14 }}>
              <div className="ah">
                <span className="badge red">Mismatch</span>
                <span className="seat">{mismatch.name}</span>
              </div>
              <div className="note">
                Confidence {(mismatch.score * 100).toFixed(0)}% (threshold{" "}
                {(mismatch.threshold * 100).toFixed(0)}%). Coordinator override required.
              </div>
              <div className="field" style={{ marginTop: 10 }}>
                <input value={reason} onChange={(e) => setReason(e.target.value)} />
              </div>
              <div className="btn-row">
                <button className="btn green sm" onClick={() => decideOverride(true)}>
                  Approve override
                </button>
                <button className="btn danger sm" onClick={() => decideOverride(false)}>
                  Deny entry
                </button>
              </div>
            </div>
          )}

          <div className="divider" />
          <table>
            <thead>
              <tr>
                <th>Seat</th>
                <th>Roll</th>
                <th>Name</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {students.slice(0, 12).map((s) => (
                <tr key={s.id}>
                  <td className="t-mono">{s.seat}</td>
                  <td className="t-mono">{s.roll_no}</td>
                  <td>{s.name}</td>
                  <td>
                    {s.checked_in ? (
                      <span className="badge green">
                        {s.override ? "Override" : "In"}{" "}
                        {s.match_score ? `${(s.match_score * 100).toFixed(0)}%` : ""}
                      </span>
                    ) : (
                      <span className="badge">Pending</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {students.length > 12 && (
            <p className="muted" style={{ marginTop: 8 }}>
              + {students.length - 12} more…
            </p>
          )}
        </div>

        <div className="card">
          <h3>🚨 IntegrityAI — Live Anomaly Feed</h3>
          <div className="feed">
            {alerts.length === 0 && (
              <div className="empty">
                No anomalies. Alerts stream here in real time during the exam.
              </div>
            )}
            {alerts.map((a, i) => (
              <div className="alert" key={i}>
                <div className="ah">
                  <span className="badge red">{a.rule}</span>
                  <span className="seat">
                    Seat {a.student.seat} · {a.student.name}
                  </span>
                  <span className="badge" style={{ marginLeft: "auto" }}>
                    {(a.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="note">{a.note}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
