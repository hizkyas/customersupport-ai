import { useState, useEffect, useRef } from 'react';
import { MessageSquare, X, Send, Headphones, ChevronDown } from 'lucide-react';
import type { Citation } from '../api/client';

interface WidgetConfig {
  organization_id: string;
  organization_name: string;
  assistant_name: string;
  company_name: string;
  tone: string;
  language: string;
  fallback_message: string;
  human_escalation_enabled: boolean;
}

interface WidgetMessage {
  id: string;
  sender_type: string;
  content: string;
  message_metadata?: { citations?: Citation[]; is_fallback?: boolean };
  created_at: string;
}

interface WidgetProps {
  orgId: string;
}

export default function Widget({ orgId }: WidgetProps) {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<WidgetConfig | null>(null);
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<WidgetMessage[]>([]);
  const [input, setInput] = useState('');
  // const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [escalating, setEscalating] = useState(false);
  const [status, setStatus] = useState<string>('ai_active');
  const bottomRef = useRef<HTMLDivElement>(null);

  // 1. Fetch public widget config & initialize session
  useEffect(() => {
    if (!orgId) return;

    fetch(`/api/v1/widget/${orgId}/config`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then((cfg: WidgetConfig) => setConfig(cfg))
      .catch(() => setConfig({
        organization_id: orgId, organization_name: 'Support', assistant_name: 'Support AI',
        company_name: 'Our Company', tone: 'professional', language: 'en',
        fallback_message: "I'm sorry, I don't have enough information.", human_escalation_enabled: true
      }));

    const savedConvId = localStorage.getItem(`widget_conv_${orgId}`);
    fetch(`/api/v1/widget/${orgId}/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ existing_conversation_id: savedConvId || undefined })
    })
      .then(r => r.json())
      .then(res => {
        setConvId(res.conversation_id);
        setStatus(res.status);
        setMessages(res.messages || []);
        localStorage.setItem(`widget_conv_${orgId}`, res.conversation_id);
      })
      .catch(() => { /* ignore */ });
  }, [orgId]);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  async function handleSend() {
    if (!input.trim() || !convId || sending) return;
    const text = input.trim();
    setInput('');
    setSending(true);

    try {
      const res = await fetch(`/api/v1/widget/${orgId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: convId, content: text })
      });
      if (res.ok) {
        const newMsgs: WidgetMessage[] = await res.json();
        setMessages(prev => [...prev, ...newMsgs]);
      }
    } catch { /* ignore */ }
    finally { setSending(false); }
  }

  async function handleEscalate() {
    if (!convId || escalating) return;
    setEscalating(true);
    try {
      const res = await fetch(`/api/v1/widget/${orgId}/escalate?conversation_id=${convId}`, {
        method: 'POST'
      });
      if (res.ok) {
        const sysMsg: WidgetMessage = await res.json();
        setMessages(prev => [...prev, sysMsg]);
        setStatus('waiting_human');
      }
    } catch { /* ignore */ }
    finally { setEscalating(false); }
  }

  return (
    <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 99999, fontFamily: 'Inter, sans-serif' }}>
      {/* Expanded Widget Window */}
      {open && (
        <div className="glass-card fade-in" style={{
          width: 380, height: 520, display: 'flex', flexDirection: 'column',
          boxShadow: '0 12px 48px rgba(0,0,0,0.6), 0 0 24px var(--accent-glow)',
          marginBottom: 16, overflow: 'hidden', border: '1px solid var(--border-strong)'
        }}>
          {/* Header */}
          <div style={{
            padding: '14px 18px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: 'linear-gradient(135deg, var(--accent), var(--violet))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16, boxShadow: '0 0 10px var(--accent-glow)'
              }}>🤖</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                  {config?.assistant_name ?? 'Support AI'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span className={`pulse-dot ${status === 'waiting_human' ? 'amber' : 'green'}`} />
                  {status === 'waiting_human' ? 'Waiting for Agent' : 'Online & AI Powered'}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              {config?.human_escalation_enabled && status !== 'waiting_human' && status !== 'human_active' && (
                <button
                  className="btn btn-ghost btn-icon btn-sm"
                  title="Connect with Human Agent"
                  onClick={handleEscalate}
                  disabled={escalating}
                >
                  <Headphones size={14} color="var(--amber)" />
                </button>
              )}
              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setOpen(false)}>
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Messages Timeline */}
          <div style={{
            flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12,
            background: 'var(--bg-base)'
          }}>
            {messages.map(m => {
              const isCust = m.sender_type === 'customer';
              const isSys = m.sender_type === 'system';
              const isAi = m.sender_type === 'ai';
              const citations = m.message_metadata?.citations ?? [];

              if (isSys) {
                return (
                  <div key={m.id} style={{ textAlign: 'center', margin: '4px 0' }}>
                    <span className="badge badge-pending" style={{ fontSize: 10, padding: '4px 10px' }}>
                      {m.content}
                    </span>
                  </div>
                );
              }

              return (
                <div key={m.id} style={{
                  display: 'flex', flexDirection: 'column',
                  alignItems: isCust ? 'flex-end' : 'flex-start', gap: 2
                }}>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', margin: '0 4px 2px' }}>
                    {isCust ? 'You' : isAi ? config?.assistant_name : 'Agent'}
                  </div>
                  <div className={`message-bubble ${isCust ? 'bubble-agent' : isAi ? 'bubble-ai' : 'bubble-customer'}`} style={{ maxWidth: '85%' }}>
                    {m.content}
                    {citations.length > 0 && (
                      <div className="citation-strip">
                        {citations.map((c, i) => (
                          <span key={i} className="citation-chip" title={`Relevance ${(c.relevance_score * 100).toFixed(0)}%`}>
                            📎 {c.document_name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {sending && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)', fontSize: 12, padding: 4 }}>
                <span className="spinner" style={{ width: 12, height: 12 }} />
                <span>{config?.assistant_name ?? 'AI'} is typing…</span>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Footer Input Bar */}
          <div style={{
            padding: 12, background: 'var(--bg-surface)', borderTop: '1px solid var(--border)',
            display: 'flex', gap: 8, alignItems: 'center'
          }}>
            <input
              type="text"
              className="input"
              style={{ fontSize: 12, padding: '8px 12px' }}
              placeholder={status === 'waiting_human' ? 'Type a message for human agent…' : 'Ask a question…'}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleSend(); }}
            />
            <button className="btn btn-primary btn-sm btn-icon" onClick={handleSend} disabled={sending || !input.trim()}>
              <Send size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Launcher Button */}
      <button
        id="widget-launcher-btn"
        className="btn btn-primary"
        style={{
          borderRadius: 99, padding: open ? '12px' : '12px 20px',
          boxShadow: '0 6px 24px var(--accent-glow), 0 0 0 1px var(--border-strong)',
          fontSize: 14, fontWeight: 700, gap: 8
        }}
        onClick={() => setOpen(o => !o)}
      >
        {open ? <ChevronDown size={20} /> : (
          <>
            <MessageSquare size={18} />
            <span>Chat Support</span>
          </>
        )}
      </button>
    </div>
  );
}
