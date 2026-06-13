import { createContext, useContext, useState, ReactNode } from "react";
import { login as apiLogin, setToken } from "./api";

export interface Session {
  role: string;
  full_name: string;
  center_id: number | null;
}

interface AuthCtx {
  session: Session | null;
  signIn: (u: string, p: string) => Promise<Session>;
  signOut: () => void;
}

const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    const raw = localStorage.getItem("es_session");
    return raw ? JSON.parse(raw) : null;
  });

  async function signIn(u: string, p: string) {
    const r = await apiLogin(u, p);
    setToken(r.access_token);
    const s: Session = { role: r.role, full_name: r.full_name, center_id: r.center_id };
    localStorage.setItem("es_session", JSON.stringify(s));
    setSession(s);
    return s;
  }

  function signOut() {
    setToken(null);
    localStorage.removeItem("es_session");
    setSession(null);
  }

  return <Ctx.Provider value={{ session, signIn, signOut }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
