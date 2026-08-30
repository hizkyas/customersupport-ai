import { BookOpen, Users, Settings, LogOut, Headphones, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

type View = 'queue' | 'kb' | 'team' | 'ai';

interface Props {
  view: View;
  setView: (v: View) => void;
}

const NAV = [
  { id: 'queue' as View, label: 'Support Queue', icon: Headphones },
  { id: 'kb'    as View, label: 'Knowledge Base', icon: BookOpen },
  { id: 'team'  as View, label: 'Team Members',   icon: Users },
  { id: 'ai'    as View, label: 'AI Settings',     icon: Settings },
];

export default function Sidebar({ view, setView }: Props) {
  const { user, org, orgs, logout, setOrg } = useAuth();
  const [orgOpen, setOrgOpen] = useState(false);

  const initials = user?.name?.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) ?? '??';

  return (
    <nav className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🤖</div>
        <div>
          <div className="sidebar-logo-text">SupportAI</div>
          <div className="sidebar-logo-sub">Admin Dashboard</div>
        </div>
      </div>

      {/* Org Selector */}
      {org && (
        <div style={{ padding: '0 4px 8px', position: 'relative' }}>
          <button
            className="btn btn-ghost w-full"
            style={{ justifyContent: 'space-between', fontSize: 12, padding: '8px 10px' }}
            onClick={() => setOrgOpen(o => !o)}
          >
            <span className="truncate" style={{ maxWidth: 140 }}>{org.name}</span>
            <ChevronDown size={12} style={{ flexShrink: 0 }} />
          </button>
          {orgOpen && orgs.length > 1 && (
            <div className="glass-card" style={{ position: 'absolute', top: '100%', left: 4, right: 4, zIndex: 50, padding: 6 }}>
              {orgs.map(o => (
                <button
                  key={o.id}
                  className="nav-item w-full"
                  style={{ fontSize: 12 }}
                  onClick={() => { setOrg(o); setOrgOpen(false); }}
                >
                  {o.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="sidebar-section-label">Navigation</div>

      {NAV.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          className={`nav-item ${view === id ? 'active' : ''}`}
          onClick={() => setView(id)}
        >
          <Icon size={16} />
          {label}
        </button>
      ))}

      <div className="sidebar-spacer" />

      {/* User footer */}
      <div className="sidebar-user">
        <div className="sidebar-avatar">{initials}</div>
        <div className="sidebar-user-info">
          <div className="sidebar-user-name">{user?.name}</div>
          <div className="sidebar-user-email">{user?.email}</div>
        </div>
        <button className="btn btn-ghost btn-icon btn-sm" onClick={logout} title="Sign out">
          <LogOut size={14} />
        </button>
      </div>
    </nav>
  );
}
