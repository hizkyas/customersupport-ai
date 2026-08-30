import { useState, useEffect, useRef, useCallback } from 'react';
import { Bot, User, AlertCircle, Clock, CheckCircle, UserCheck, RefreshCw, Send, Sparkles, StickyNote } from 'lucide-react';
import { api, type Conversation, type Message, type Note, type Citation } from '../api/client';
import { useAuth } from '../context/AuthContext';

const STATUS_LABELS: Record<string, string> = {
  active: 'Active', waiting_human: 'Waiting', human_active: 'Human Active',
  resolved: 'Resolved', closed: 'Closed', transferred: 'Transferred',
};
const PRIORITY_COLORS: Record<string, string> = { low: '#64748b', normal: '#6366f1', high: '#f59e0b', urgent: '#f43f5e' };

function statusBadge(status: string) {
  const cls = { active: 'badge-ai', waiting_human: 'badge-pending', human_active: 'badge-human', resolved: 'badge-ready', closed: 'badge-ready', transferred: 'badge-agent' }[status] ?? 'badge-ai';
  return <span className={`badge ${cls}`}>{STATUS_LABELS[status] ?? status}</span>;
}

function SenderIcon({ type }: { type: string }) {
  if (type === 'ai')     return <Bot size={12} />;
  if (type === 'agent')  return <UserCheck size={12} />;
  if (type === 'customer') return <User size={12} />;
  return <AlertCircle size={12} />;
}

function MessageRow({ msg }: { msg: Message }) {
  const type = msg.sender_type; // customer | ai | agent | system | human_agent
  const realType = type === 'human_agent' ? 'agent' : type;
  const isNote = msg.message_type === 'internal_note';
  const row = isNote ? 'note' : realType;
  const bubbleCls = isNote ? 'bubble-note' : `bubble-${realType}`;
  const citations: Citation[] = msg.message_metadata?.citations ?? [];

  if (realType === 'system') {
    return (
      <div className="message-row system">
        <div className={`message-bubble bubble-system`}>{msg.content}</div>
      </div>
    );
  }

  return (
    <div className={`message-row ${row} fade-in`}>
      <div className="message-sender">
        <SenderIcon type={realType} />
        {isNote ? '📌 Internal Note' : realType === 'ai' ? 'AI Assistant' : realType === 'agent' ? 'Support Agent' : 'Customer'}
        <span className="message-time">{new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
      </div>
      <div className={`message-bubble ${bubbleCls}`}>
        {msg.content}
        {citations.length > 0 && (
          <div className="citation-strip">
            {citations.map((c, i) => (
              <span key={i} className="citation-chip" title={`Chunk ${c.chunk_index} — relevance ${(c.relevance_score * 100).toFixed(0)}%`}>
                📎 {c.document_name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function SupportQueueView() {
  const { org } = useAuth();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [messages, setMessages]  = useState<Message[]>([]);
  const [notes, setNotes]        = useState<Note[]>([]);
  const [loading, setLoading]    = useState(false);
  const [sending, setSending]    = useState(false);
  const [replyText, setReplyText] = useState('');
  const [replyMode, setReplyMode] = useState<'reply' | 'note'>('reply');
  const [suggestion, setSuggestion] = useState<{ text: string; citations: Citation[]; confidence: number } | null>(null);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadQueue = useCallback(async () => {
    if (!org) return;
    try {
      const data = await api.conversations.queue(org.id);
      setConversations(data);
    } catch { /* ignore */ }
  }, [org]);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  useEffect(() => {
    if (!selected) return;
    setMessages([]); setNotes([]); setError('');
    Promise.all([api.conversations.messages(selected.id), api.conversations.notes(selected.id)])
      .then(([msgs, ns]) => { setMessages(msgs); setNotes(ns); })
      .catch(e => setError(e.message));
  }, [selected]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const allMessages = [...messages, ...notes.map(n => ({
    id: n.id, conversation_id: n.conversation_id, sender_type: 'agent', sender_id: n.agent_id,
    content: n.content, message_type: 'internal_note',
    message_metadata: null, created_at: n.created_at,
  } as Message))].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

  const filtered = conversations.filter(c => filter === 'all' || c.status === filter);

  async function handleSend() {
    if (!selected || !replyText.trim()) return;
    setSending(true);
    try {
      if (replyMode === 'reply') {
        const msg = await api.conversations.reply(selected.id, replyText);
        setMessages(m => [...m, msg]);
      } else {
        const note = await api.conversations.addNote(selected.id, replyText);
        setNotes(n => [...n, note]);
      }
      setReplyText(''); setSuggestion(null);
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setSending(false); }
  }

  async function handleSuggest() {
    if (!selected) return;
    setSuggestLoading(true);
    try {
      const res = await api.conversations.suggestReply(selected.id);
      setSuggestion({ text: res.suggested_reply, citations: res.citations, confidence: res.confidence_score });
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setSuggestLoading(false); }
  }

  async function handleAssign() {
    if (!selected) return;
    setLoading(true);
    try {
      const updated = await api.conversations.assign(selected.id);
      setSelected(updated);
      setConversations(cs => cs.map(c => c.id === updated.id ? updated : c));
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setLoading(false); }
  }

  async function handleResolve() {
    if (!selected) return;
    setLoading(true);
    try {
      const updated = await api.conversations.resolve(selected.id);
      setSelected(updated);
      setConversations(cs => cs.map(c => c.id === updated.id ? updated : c));
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setLoading(false); }
  }

  async function handleReopen() {
    if (!selected) return;
    setLoading(true);
    try {
      const updated = await api.conversations.reopen(selected.id);
      setSelected(updated);
      setConversations(cs => cs.map(c => c.id === updated.id ? updated : c));
    } catch (e: unknown) { setError((e as Error).message); }
    finally { setLoading(false); }
  }

  const FILTERS = [
    { id: 'all', label: 'All' },
    { id: 'waiting_human', label: 'Waiting' },
    { id: 'human_active', label: 'Active' },
    { id: 'resolved', label: 'Resolved' },
  ];

  return (
    <div className="queue-shell">
      {/* Left: list */}
      <div className="queue-list">
        <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 13, fontWeight: 700 }}>Support Queue</span>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={loadQueue} title="Refresh"><RefreshCw size={13} /></button>
        </div>
        <div className="queue-filters">
          {FILTERS.map(f => (
            <button key={f.id} className={`filter-chip ${filter === f.id ? 'active' : ''}`} onClick={() => setFilter(f.id)}>{f.label}</button>
          ))}
        </div>
        {filtered.length === 0 && (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
            <CheckCircle size={28} style={{ opacity: 0.3, margin: '0 auto 8px' }} />
            <div>No conversations found</div>
          </div>
        )}
        {filtered.map(conv => (
          <div key={conv.id}
            className={`ticket-item ${selected?.id === conv.id ? 'active' : ''}`}
            onClick={() => setSelected(conv)}
          >
            <div className="ticket-item-header">
              <span className="ticket-id">{conv.id.slice(0, 8)}…</span>
              {statusBadge(conv.status)}
            </div>
            <div className="ticket-preview">{conv.channel} · {conv.priority}</div>
            <div className="ticket-meta">
              <Clock size={10} style={{ display: 'inline', marginRight: 3 }} />
              {new Date(conv.updated_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
              {conv.priority === 'urgent' && <span style={{ color: 'var(--rose)', marginLeft: 6 }}>⚡ Urgent</span>}
            </div>
          </div>
        ))}
      </div>

      {/* Right: conversation panel */}
      <div className="conv-panel">
        {!selected ? (
          <div className="conv-empty">
            <div className="conv-empty-icon">💬</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Select a conversation</div>
            <div style={{ fontSize: 12 }}>Pick a ticket from the queue to get started</div>
          </div>
        ) : (
          <>
            <div className="conv-header">
              <div>
                <div style={{ fontSize: 13, fontWeight: 700 }}>Conversation <code style={{ fontSize: 11, color: 'var(--text-muted)' }}>{selected.id.slice(0, 12)}…</code></div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'flex', gap: 8, alignItems: 'center' }}>
                  {statusBadge(selected.status)}
                  <span style={{ color: PRIORITY_COLORS[selected.priority] }}>● {selected.priority}</span>
                  <span>via {selected.channel}</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {(selected.status === 'active' || selected.status === 'waiting_human') && (
                  <button className="btn btn-secondary btn-sm" onClick={handleAssign} disabled={loading}>
                    <UserCheck size={12} /> Assign to Me
                  </button>
                )}
                {selected.status !== 'resolved' && selected.status !== 'closed' && (
                  <button className="btn btn-success btn-sm" onClick={handleResolve} disabled={loading}>
                    <CheckCircle size={12} /> Resolve
                  </button>
                )}
                {(selected.status === 'resolved' || selected.status === 'closed') && (
                  <button className="btn btn-secondary btn-sm" onClick={handleReopen} disabled={loading}>
                    <RefreshCw size={12} /> Reopen
                  </button>
                )}
              </div>
            </div>

            {error && <div style={{ padding: '8px 20px', background: 'rgba(244,63,94,0.1)', color: 'var(--rose)', fontSize: 12 }}>{error}</div>}

            <div className="conv-timeline">
              {allMessages.map(m => <MessageRow key={m.id} msg={m} />)}
              <div ref={bottomRef} />
            </div>

            {/* AI Suggestion Banner */}
            {suggestion && (
              <div style={{ padding: '0 20px 12px' }}>
                <div className="suggest-banner fade-in">
                  <div className="suggest-banner-label">✨ AI Suggested Reply</div>
                  <div style={{ marginBottom: 10, lineHeight: 1.6 }}>{suggestion.text}</div>
                  {suggestion.citations.length > 0 && (
                    <div className="citation-strip" style={{ marginBottom: 10 }}>
                      {suggestion.citations.map((c, i) => <span key={i} className="citation-chip">📎 {c.document_name}</span>)}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-primary btn-sm" onClick={() => { setReplyText(suggestion.text); setSuggestion(null); setReplyMode('reply'); }}>
                      Use This Reply
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setSuggestion(null)}>Dismiss</button>
                    <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center' }}>
                      Confidence: {(suggestion.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Reply Box */}
            <div className="reply-box">
              <div className="reply-tabs">
                <button className={`reply-tab ${replyMode === 'reply' ? 'active' : ''}`} onClick={() => setReplyMode('reply')}>
                  <Send size={11} style={{ display: 'inline', marginRight: 4 }} />Reply
                </button>
                <button className={`reply-tab ${replyMode === 'note' ? 'active' : ''}`} onClick={() => setReplyMode('note')}>
                  <StickyNote size={11} style={{ display: 'inline', marginRight: 4 }} />Internal Note
                </button>
              </div>
              <textarea
                className="textarea"
                style={{ minHeight: 70 }}
                placeholder={replyMode === 'reply' ? 'Type your reply…' : 'Add an internal note (not visible to customer)…'}
                value={replyText}
                onChange={e => setReplyText(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSend(); }}
              />
              <div className="reply-actions">
                <button className="btn btn-secondary btn-sm" onClick={handleSuggest} disabled={suggestLoading}>
                  {suggestLoading ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <Sparkles size={12} />}
                  AI Suggest
                </button>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Ctrl+Enter to send</span>
                  <button className="btn btn-primary btn-sm" onClick={handleSend} disabled={sending || !replyText.trim()}>
                    {sending ? <span className="spinner" style={{ width: 12, height: 12 }} /> : <Send size={12} />}
                    {replyMode === 'reply' ? 'Send' : 'Add Note'}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
