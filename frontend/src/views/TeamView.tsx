import { useState, useEffect, useCallback } from 'react';
import { UserPlus, RefreshCw } from 'lucide-react';
import { api, type Member } from '../api/client';
import { useAuth } from '../context/AuthContext';

const ROLES = ['owner', 'admin', 'agent'];

export default function TeamView() {
  const { org } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Add member form
  const [email, setEmail] = useState('');
  const [role, setRole]   = useState('agent');
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const loadMembers = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try { setMembers(await api.orgs.members(org.id)); }
    catch (e: unknown) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [org]);

  useEffect(() => { loadMembers(); }, [loadMembers]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    setAdding(true); setError(''); setSuccess('');
    try {
      await api.orgs.addMember(org.id, { email, role });
      setSuccess(`Invited ${email} as ${role}`);
      setEmail(''); setShowForm(false);
      await loadMembers();
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setAdding(false); }
  }

  return (
    <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Team Members</h1>
          <p className="page-subtitle">{members.length} member{members.length !== 1 ? 's' : ''}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={loadMembers} disabled={loading}>
            <RefreshCw size={13} /> Refresh
          </button>
          <button id="invite-member-btn" className="btn btn-primary btn-sm" onClick={() => setShowForm(f => !f)}>
            <UserPlus size={13} /> Invite Member
          </button>
        </div>
      </div>

      <div className="page-body">
        {error   && <div className="glass-card" style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', color: 'var(--rose)', padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>{error}</div>}
        {success && <div className="glass-card" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', color: 'var(--emerald)', padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>{success}</div>}

        {showForm && (
          <div className="glass-card fade-in" style={{ padding: 20, marginBottom: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 14 }}>Invite New Member</div>
            <form onSubmit={handleAdd} style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ flex: 2, minWidth: 200 }}>
                <label className="form-label">Email</label>
                <input id="member-email" type="email" className="input" placeholder="colleague@company.com"
                  value={email} onChange={e => setEmail(e.target.value)} required />
              </div>
              <div className="form-group" style={{ flex: 1, minWidth: 120 }}>
                <label className="form-label">Role</label>
                <select id="member-role" className="select" value={role} onChange={e => setRole(e.target.value)}>
                  {ROLES.map(r => <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 1 }}>
                <button id="add-member-submit" type="submit" className="btn btn-primary btn-sm" disabled={adding}>
                  {adding ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <UserPlus size={12} />} Invite
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>Cancel</button>
              </div>
            </form>
          </div>
        )}

        <div className="glass-card" style={{ overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <div className="spinner" style={{ margin: '0 auto 12px', width: 24, height: 24 }} />
              Loading members…
            </div>
          ) : members.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center' }}>
              <UserPlus size={40} style={{ opacity: 0.2, margin: '0 auto 12px', display: 'block' }} />
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>No members yet</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Invite your first team member above</div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Member</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Joined</th>
                </tr>
              </thead>
              <tbody>
                {members.map(m => {
                  const initials = m.user.name?.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) ?? '??';
                  return (
                    <tr key={m.user.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div className="sidebar-avatar" style={{ width: 30, height: 30, fontSize: 11 }}>{initials}</div>
                          <span style={{ fontWeight: 600 }}>{m.user.name}</span>
                        </div>
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{m.user.email}</td>
                      <td><span className={`badge badge-${m.role}`}>{m.role}</span></td>
                      <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{new Date(m.created_at).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
