import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function AuthView() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState<'login' | 'register'>('login');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Login
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPass,  setLoginPass]  = useState('');

  // Register
  const [regName,  setRegName]  = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPass,  setRegPass]  = useState('');
  const [regOrg,   setRegOrg]   = useState('');

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(''); setLoading(true);
    try { await login(loginEmail, loginPass); }
    catch (err: unknown) { setError((err as Error).message); }
    finally { setLoading(false); }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(''); setLoading(true);
    try { await register(regEmail, regPass, regName, regOrg); }
    catch (err: unknown) { setError((err as Error).message); }
    finally { setLoading(false); }
  }

  return (
    <div className="auth-shell">
      <div className="auth-glow" />
      <div className="auth-card fade-in">
        <div className="auth-logo">
          <div className="auth-logo-icon">🤖</div>
          <div className="auth-logo-title">Support<span>AI</span></div>
        </div>

        <div className="auth-tabs">
          <button className={`auth-tab ${tab === 'login'    ? 'active' : ''}`} onClick={() => { setTab('login');    setError(''); }}>Sign In</button>
          <button className={`auth-tab ${tab === 'register' ? 'active' : ''}`} onClick={() => { setTab('register'); setError(''); }}>Create Account</button>
        </div>

        {tab === 'login' ? (
          <form onSubmit={handleLogin} className="flex-col gap-3" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input id="login-email" type="email" className="input" placeholder="you@company.com"
                value={loginEmail} onChange={e => setLoginEmail(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input id="login-password" type="password" className="input" placeholder="••••••••"
                value={loginPass} onChange={e => setLoginPass(e.target.value)} required />
            </div>
            {error && <p className="form-error">{error}</p>}
            <button id="login-submit" type="submit" className="btn btn-primary w-full" disabled={loading} style={{ marginTop: 4 }}>
              {loading ? <span className="spinner" /> : 'Sign In'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="flex-col" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="form-group">
              <label className="form-label">Full Name</label>
              <input id="reg-name" type="text" className="input" placeholder="Jane Smith"
                value={regName} onChange={e => setRegName(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input id="reg-email" type="email" className="input" placeholder="you@company.com"
                value={regEmail} onChange={e => setRegEmail(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input id="reg-password" type="password" className="input" placeholder="Min 8 characters"
                value={regPass} onChange={e => setRegPass(e.target.value)} required minLength={8} />
            </div>
            <div className="form-group">
              <label className="form-label">Organization Name</label>
              <input id="reg-org" type="text" className="input" placeholder="Acme Inc."
                value={regOrg} onChange={e => setRegOrg(e.target.value)} required />
            </div>
            {error && <p className="form-error">{error}</p>}
            <button id="reg-submit" type="submit" className="btn btn-primary w-full" disabled={loading} style={{ marginTop: 4 }}>
              {loading ? <span className="spinner" /> : 'Create Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
