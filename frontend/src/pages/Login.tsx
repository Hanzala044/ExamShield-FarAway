import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Login() {
  const { signIn } = useAuth();
  const nav = useNavigate();
  const [u, setU] = useState("admin");
  const [p, setP] = useState("admin123");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const s = await signIn(u, p);
      nav(s.role === "super_admin" ? "/admin" : "/center");
    } catch (e: any) {
      setErr(e.message || "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="brand">
          Exam<span>Shield</span>
        </div>
        <div className="login-sub">Secure CBT Infrastructure · Staff Console</div>
        <div className="field">
          <label>Username</label>
          <input value={u} onChange={(e) => setU(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={p} onChange={(e) => setP(e.target.value)} />
        </div>
        <button className="btn primary" style={{ width: "100%" }} disabled={busy}>
          {busy ? <span className="spinner" /> : "Sign in"}
        </button>
        {err && <div className="err">{err}</div>}
        <div className="cred-hint">
          <b>Demo accounts</b> (password in parentheses):
          <br />
          admin (admin123) · coord1 (coord123) · invig1 (invig123)
          <br />
          Students take the exam at <b>/kiosk</b>; anyone can view <b>/audit</b>.
        </div>
      </form>
    </div>
  );
}
