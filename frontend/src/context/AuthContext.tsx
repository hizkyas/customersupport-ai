import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { api, type Org } from '../api/client';

interface User { id: string; email: string; name: string; }

interface AuthCtx {
  user: User | null;
  org: Org | null;
  orgs: Org[];
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, orgName: string) => Promise<void>;
  logout: () => void;
  setOrg: (org: Org) => void;
  refreshOrgs: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [org, setOrg] = useState<Org | null>(null);
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [loading, setLoading] = useState(true);

  async function refreshOrgs() {
    try {
      const list = await api.orgs.list();
      setOrgs(list);
      if (list.length > 0 && !org) setOrg(list[0]);
    } catch { /* ignore */ }
  }

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) { setLoading(false); return; }
    api.auth.me()
      .then(u => { setUser(u); return refreshOrgs(); })
      .catch(() => { localStorage.removeItem('token'); })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const data = await api.auth.login(email, password);
    localStorage.setItem('token', data.access_token);
    const u = await api.auth.me();
    setUser(u);
    await refreshOrgs();
  }

  async function register(email: string, password: string, name: string, orgName: string) {
    await api.auth.register({ email, password, name, organization_name: orgName });
    await login(email, password);
  }

  function logout() {
    localStorage.removeItem('token');
    setUser(null); setOrg(null); setOrgs([]);
  }

  return (
    <AuthContext.Provider value={{ user, org, orgs, loading, login, register, logout, setOrg, refreshOrgs }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
