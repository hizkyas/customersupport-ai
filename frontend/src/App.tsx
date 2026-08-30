import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthView from './views/AuthView';
import Sidebar from './components/Sidebar';
import SupportQueueView from './views/SupportQueueView';
import KnowledgeBaseView from './views/KnowledgeBaseView';
import TeamView from './views/TeamView';
import AISettingsView from './views/AISettingsView';
import Widget from './components/Widget';
import './index.css';

type View = 'queue' | 'kb' | 'team' | 'ai';

function Dashboard() {
  const [view, setView] = useState<View>('queue');
  const { org } = useAuth();

  return (
    <div className="app-shell">
      <Sidebar view={view} setView={setView} />
      <div className="main-content">
        {view === 'queue' && <SupportQueueView />}
        {view === 'kb'    && <KnowledgeBaseView />}
        {view === 'team'  && <TeamView />}
        {view === 'ai'    && <AISettingsView />}
      </div>
      {org && <Widget orgId={org.id} />}
    </div>
  );
}

function AppInner() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16 }}>
        <div style={{
          width: 48, height: 48,
          background: 'linear-gradient(135deg, var(--accent), var(--violet))',
          borderRadius: 12,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 24,
          boxShadow: '0 0 24px var(--accent-glow)',
          animation: 'pulse 1.4s ease-in-out infinite'
        }}>🤖</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading…</div>
      </div>
    );
  }

  return user ? <Dashboard /> : <AuthView />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}
