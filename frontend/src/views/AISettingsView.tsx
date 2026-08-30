import { useState, useCallback, useEffect } from 'react';
import { Save, RefreshCw, Bot, Shield, MessageSquare, Code } from 'lucide-react';
import { api, type AIConfig } from '../api/client';
import { useAuth } from '../context/AuthContext';
import WidgetEmbedModal from '../components/WidgetEmbedModal';

const TONES = ['professional', 'friendly', 'formal', 'casual', 'empathetic'];
const LANGS = ['en', 'fr', 'de', 'es', 'pt', 'ar', 'ja', 'zh'];

export default function AISettingsView() {
  const { org } = useAuth();
  const [config, setConfig] = useState<AIConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState('');
  const [success, setSuccess] = useState('');
  const [showEmbed, setShowEmbed] = useState(false);

  const [form, setForm] = useState({
    assistant_name: '', company_name: '', system_prompt: '',
    tone: 'professional', language: 'en', fallback_message: '',
    confidence_threshold: 0.7, human_escalation_enabled: true,
  });

  const loadConfig = useCallback(async () => {
    if (!org) return;
    setLoading(true); setError('');
    try {
      const cfg = await api.aiConfig.get(org.id);
      setConfig(cfg);
      setForm({
        assistant_name: cfg.assistant_name,
        company_name: cfg.company_name ?? '',
        system_prompt: cfg.system_prompt ?? '',
        tone: cfg.tone,
        language: cfg.language,
        fallback_message: cfg.fallback_message,
        confidence_threshold: cfg.confidence_threshold,
        human_escalation_enabled: cfg.human_escalation_enabled,
      });
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [org]);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  function update(key: string, val: unknown) {
    setForm(f => ({ ...f, [key]: val }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    setSaving(true); setError(''); setSuccess('');
    try {
      const updated = await api.aiConfig.update(org.id, form);
      setConfig(updated);
      setSuccess('AI settings saved successfully.');
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  if (loading) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
      <div className="spinner" style={{ width: 28, height: 28 }} />
    </div>
  );

  return (
    <div style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {showEmbed && org && (
        <WidgetEmbedModal orgId={org.id} orgName={org.name} onClose={() => setShowEmbed(false)} />
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">AI Settings</h1>
          <p className="page-subtitle">Configure your AI assistant's behavior and personality</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {org && (
            <button className="btn btn-primary btn-sm" onClick={() => setShowEmbed(true)}>
              <Code size={13} /> Embed Widget Code
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={loadConfig}><RefreshCw size={13} /> Refresh</button>
        </div>
      </div>

      <div className="page-body">
        {error   && <div className="glass-card" style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', color: 'var(--rose)', padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>{error}</div>}
        {success && <div className="glass-card" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', color: 'var(--emerald)', padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>{success}</div>}

        {!config && !loading && (
          <div className="glass-card" style={{ padding: '24px', marginBottom: 16, color: 'var(--text-muted)', fontSize: 13 }}>
            No AI configuration found for this organization. Settings will be created on first save.
          </div>
        )}

        <form id="ai-settings-form" onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Identity */}
          <div className="glass-card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--accent-light)' }}>
              <Bot size={15} /> Identity
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div className="form-group">
                <label className="form-label">Assistant Name</label>
                <input id="ai-name" type="text" className="input" placeholder="Aria" value={form.assistant_name}
                  onChange={e => update('assistant_name', e.target.value)} required />
              </div>
              <div className="form-group">
                <label className="form-label">Company Name</label>
                <input id="ai-company" type="text" className="input" placeholder="Acme Inc." value={form.company_name}
                  onChange={e => update('company_name', e.target.value)} />
              </div>
            </div>
          </div>

          {/* Personality */}
          <div className="glass-card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--accent-light)' }}>
              <MessageSquare size={15} /> Personality & Language
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
              <div className="form-group">
                <label className="form-label">Tone</label>
                <select id="ai-tone" className="select" value={form.tone} onChange={e => update('tone', e.target.value)}>
                  {TONES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Primary Language</label>
                <select id="ai-language" className="select" value={form.language} onChange={e => update('language', e.target.value)}>
                  {LANGS.map(l => <option key={l} value={l}>{l.toUpperCase()}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">System Prompt</label>
              <textarea id="ai-system-prompt" className="textarea" style={{ minHeight: 120 }}
                placeholder="You are a helpful customer support assistant for {company}. Always be polite and reference relevant documentation when possible."
                value={form.system_prompt}
                onChange={e => update('system_prompt', e.target.value)} />
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Additional instructions that shape the AI's behavior for your organization.</div>
            </div>
          </div>

          {/* Confidence & Escalation */}
          <div className="glass-card" style={{ padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, fontSize: 13, fontWeight: 700, color: 'var(--accent-light)' }}>
              <Shield size={15} /> Quality & Escalation
            </div>
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <label className="form-label" style={{ margin: 0 }}>Confidence Threshold</label>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-light)' }}>{Math.round(form.confidence_threshold * 100)}%</span>
              </div>
              <input id="ai-confidence" type="range" min={0} max={1} step={0.05}
                value={form.confidence_threshold}
                onChange={e => update('confidence_threshold', parseFloat(e.target.value))} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                <span>Low (answer more)</span><span>High (escalate more)</span>
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">Fallback Message</label>
              <textarea id="ai-fallback" className="textarea" style={{ minHeight: 70 }}
                placeholder="I'm sorry, I don't have enough information to answer that. Let me connect you with a human agent."
                value={form.fallback_message}
                onChange={e => update('fallback_message', e.target.value)} />
            </div>

            <label className="toggle">
              <input id="ai-escalation-toggle" type="checkbox"
                checked={form.human_escalation_enabled}
                onChange={e => update('human_escalation_enabled', e.target.checked)} />
              <div className="toggle-track"><div className="toggle-thumb" /></div>
              <span style={{ fontSize: 13 }}>Enable Human Escalation</span>
            </label>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, marginLeft: 50 }}>
              Allow AI to escalate conversations to the human support queue when confidence is low.
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button id="ai-settings-save" type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Save size={14} />}
              Save Settings
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
