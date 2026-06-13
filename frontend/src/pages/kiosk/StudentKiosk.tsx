import { useEffect, useRef, useState } from "react";
import { apiPost } from "../../api";

interface Q {
  idx: number;
  section: string;
  text: string;
  options: string[];
}

export default function StudentKiosk() {
  const [token, setToken] = useState(
    () => new URLSearchParams(location.search).get("token") || ""
  );
  const [phase, setPhase] = useState<"enter" | "locked" | "exam" | "done">("enter");
  const [info, setInfo] = useState<any>(null);
  const [questions, setQuestions] = useState<Q[]>([]);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [cur, setCur] = useState(0);
  const [left, setLeft] = useState(0);
  const [err, setErr] = useState("");
  const shownAt = useRef<number>(Date.now());
  const changes = useRef<Record<number, number>>({});

  async function start() {
    setErr("");
    try {
      const r = await apiPost("/session/start", { session_token: token });
      setInfo(r);
      setQuestions(r.questions);
      setLeft(r.exam.duration_min * 60);
      setPhase("exam");
      shownAt.current = Date.now();
    } catch (e: any) {
      if (String(e.message).toLowerCase().includes("locked")) {
        setPhase("locked");
        setErr(e.message);
      } else {
        setErr(e.message);
      }
    }
  }

  // timer + auto-submit
  useEffect(() => {
    if (phase !== "exam") return;
    const t = setInterval(() => {
      setLeft((s) => {
        if (s <= 1) {
          clearInterval(t);
          submit(true);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [phase]);

  // kiosk lockdown: disable context menu/copy + tab-switch detection
  useEffect(() => {
    if (phase !== "exam") return;
    const block = (e: Event) => e.preventDefault();
    const onBlur = () => {
      const q = questions[cur];
      apiPost("/session/telemetry", {
        session_token: token,
        q_idx: q?.idx,
        tab_switch: true,
      }).catch(() => {});
    };
    document.addEventListener("contextmenu", block);
    document.addEventListener("copy", block);
    window.addEventListener("blur", onBlur);
    return () => {
      document.removeEventListener("contextmenu", block);
      document.removeEventListener("copy", block);
      window.removeEventListener("blur", onBlur);
    };
  }, [phase, cur, questions, token]);

  function choose(qIdx: number, opt: number) {
    const responseMs = Date.now() - shownAt.current;
    const prev = answers[qIdx];
    changes.current[qIdx] = (changes.current[qIdx] || 0) + (prev !== undefined ? 1 : 0);
    setAnswers((a) => ({ ...a, [qIdx]: opt }));
    apiPost("/session/telemetry", {
      session_token: token,
      q_idx: qIdx,
      chosen: opt,
      response_ms: responseMs,
      change_count: changes.current[qIdx],
      tab_switch: false,
    }).catch(() => {});
  }

  function go(i: number) {
    setCur(i);
    shownAt.current = Date.now();
  }

  async function submit(auto = false) {
    try {
      const r = await apiPost("/session/submit", {
        session_token: token,
        answers: Object.fromEntries(Object.entries(answers).map(([k, v]) => [k, v])),
      });
      setInfo((p: any) => ({ ...p, result: r, auto }));
      setPhase("done");
    } catch (e: any) {
      setErr(e.message);
    }
  }

  const mmss = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  if (phase === "enter")
    return (
      <div className="kiosk">
        <div className="kiosk-lock">
          <div className="lock-ico">🔒</div>
          <div className="big">ExamShield Kiosk</div>
          <p style={{ opacity: 0.7, maxWidth: 420 }}>
            Enter the session token issued at check-in. The exam stays locked until the
            center's time-lock clears.
          </p>
          <input
            style={{ maxWidth: 360, color: "#0C0C0C" }}
            placeholder="sess_…"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <button className="btn primary" onClick={start} disabled={!token}>
            Enter Exam
          </button>
          {err && <div className="err">{err}</div>}
        </div>
      </div>
    );

  if (phase === "locked")
    return (
      <div className="kiosk">
        <div className="kiosk-lock">
          <div className="lock-ico">⏳</div>
          <div className="big">Exam is locked</div>
          <p style={{ opacity: 0.75, maxWidth: 460 }}>{err}</p>
          <p style={{ opacity: 0.5 }}>
            The paper exists only as an encrypted blob until the coordinator releases the
            time-locked key.
          </p>
          <button className="btn primary" onClick={start}>
            Retry
          </button>
        </div>
      </div>
    );

  if (phase === "done")
    return (
      <div className="kiosk">
        <div className="kiosk-lock">
          <div className="lock-ico">✅</div>
          <div className="big">Submitted</div>
          <p style={{ opacity: 0.75 }}>
            {info?.auto ? "Time expired — auto-submitted." : "Your responses are recorded."}{" "}
            {info?.result?.answered} answers · checksum locked.
          </p>
          <p className="hashstr" style={{ opacity: 0.6, maxWidth: 480 }}>
            {info?.result?.checksum}
          </p>
        </div>
      </div>
    );

  const q = questions[cur];
  return (
    <div className="kiosk">
      <div className="kiosk-top">
        <b>{info?.exam?.name}</b>
        <span className="badge">{info?.student?.name}</span>
        <span className="badge">Seat {info?.student?.seat}</span>
        <span className="kiosk-timer">{mmss(left)}</span>
      </div>
      <div className="kiosk-body">
        <div className="q-card">
          <div style={{ opacity: 0.6, fontSize: 12, marginBottom: 8 }}>
            {q.section} · Question {cur + 1} of {questions.length}
          </div>
          <div className="q-text">{q.text}</div>
          {q.options.map((o, i) => (
            <div
              key={i}
              className={`opt ${answers[q.idx] === i ? "sel" : ""}`}
              onClick={() => choose(q.idx, i)}
            >
              <b style={{ width: 18 }}>{String.fromCharCode(65 + i)}</b>
              {o}
            </div>
          ))}
          <div className="btn-row" style={{ marginTop: 18 }}>
            <button className="btn sm" disabled={cur === 0} onClick={() => go(cur - 1)}>
              ← Prev
            </button>
            <button
              className="btn sm"
              disabled={cur === questions.length - 1}
              onClick={() => go(cur + 1)}
            >
              Next →
            </button>
            <button className="btn green sm" style={{ marginLeft: "auto" }} onClick={() => submit(false)}>
              Submit Exam
            </button>
          </div>
        </div>

        <div className="kiosk-side">
          <h4>Question Palette</h4>
          <div className="palette">
            {questions.map((qq, i) => (
              <button
                key={qq.idx}
                className={`pbtn ${answers[qq.idx] !== undefined ? "answered" : ""} ${
                  i === cur ? "current" : ""
                }`}
                onClick={() => go(i)}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <p style={{ opacity: 0.5, fontSize: 11, marginTop: 14 }}>
            Right-click, copy, and tab-switching are disabled and logged. Hard questions
            answered in under 2s are flagged to invigilators.
          </p>
        </div>
      </div>
    </div>
  );
}
