import { Navigate, Route, Routes, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import AdminPortal from "./pages/admin/AdminPortal";
import CenterDashboard from "./pages/center/CenterDashboard";
import StudentKiosk from "./pages/kiosk/StudentKiosk";
import AuditTrail from "./pages/public/AuditTrail";

function Shell({ children }: { children: React.ReactNode }) {
  const { session, signOut } = useAuth();
  const nav = useNavigate();
  return (
    <>
      <div className="topbar">
        <span className="brand">
          Exam<span>Shield</span>
        </span>
        <nav>
          {session?.role === "super_admin" && (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? "active" : "")}>
              NTA Admin
            </NavLink>
          )}
          {session && (
            <NavLink to="/center" className={({ isActive }) => (isActive ? "active" : "")}>
              Center Console
            </NavLink>
          )}
          <NavLink to="/audit" className={({ isActive }) => (isActive ? "active" : "")}>
            Public Audit
          </NavLink>
        </nav>
        <div className="right">
          {session ? (
            <>
              <span>
                <b>{session.full_name}</b> · {session.role}
              </span>
              <button
                className="btn sm"
                onClick={() => {
                  signOut();
                  nav("/login");
                }}
              >
                Sign out
              </button>
            </>
          ) : (
            <NavLink to="/login" className="btn sm">
              Staff sign in
            </NavLink>
          )}
        </div>
      </div>
      <div className="wrap">{children}</div>
    </>
  );
}

function Protected({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const { session } = useAuth();
  if (!session) return <Navigate to="/login" replace />;
  if (!roles.includes(session.role)) return <Navigate to="/center" replace />;
  return <>{children}</>;
}

export default function App() {
  const { session } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* Kiosk: standalone, token-based, no staff auth */}
      <Route path="/kiosk" element={<StudentKiosk />} />
      {/* Public audit: no auth, but inside shell for navigation */}
      <Route path="/audit" element={<Shell><AuditTrail /></Shell>} />
      <Route
        path="/admin"
        element={
          <Shell>
            <Protected roles={["super_admin"]}>
              <AdminPortal />
            </Protected>
          </Shell>
        }
      />
      <Route
        path="/center"
        element={
          <Shell>
            <Protected roles={["super_admin", "coordinator", "invigilator"]}>
              <CenterDashboard />
            </Protected>
          </Shell>
        }
      />
      <Route
        path="*"
        element={
          <Navigate
            to={session ? (session.role === "super_admin" ? "/admin" : "/center") : "/audit"}
            replace
          />
        }
      />
    </Routes>
  );
}
