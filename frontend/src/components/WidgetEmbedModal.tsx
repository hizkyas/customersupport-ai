import { useState } from 'react';
import { X, Copy, Check } from 'lucide-react';

interface Props {
  orgId: string;
  orgName: string;
  onClose: () => void;
}

export default function WidgetEmbedModal({ orgId, orgName, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  const snippet = `<!-- SupportAI Customer Support Widget -->
<script
  src="${window.location.origin}/widget.js"
  data-organization-id="${orgId}"
  async>
</script>`;

  function handleCopy() {
    navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(10,15,30,0.8)',
      backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16
    }}>
      <div className="glass-card fade-in" style={{ width: '100%', maxWidth: 540, padding: 24, position: 'relative' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 34, height: 34, borderRadius: 8,
              background: 'linear-gradient(135deg, var(--accent), var(--violet))',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16
            }}>⚡</div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>Embed Chat Widget</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{orgName}</div>
            </div>
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose}><X size={16} /></button>
        </div>

        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.5 }}>
          Paste this snippet before the closing <code>&lt;/body&gt;</code> tag on any website to embed your AI support assistant.
        </p>

        <div style={{ position: 'relative', marginBottom: 16 }}>
          <pre style={{
            background: 'var(--bg-base)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)',
            padding: '14px 16px', fontSize: 12, color: 'var(--accent-light)', fontFamily: 'monospace', overflowX: 'auto',
            lineHeight: 1.6
          }}>
            {snippet}
          </pre>
          <button
            className={`btn ${copied ? 'btn-success' : 'btn-secondary'} btn-sm`}
            style={{ position: 'absolute', top: 10, right: 10 }}
            onClick={handleCopy}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Copied!' : 'Copy Code'}
          </button>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn-primary btn-sm" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}
