import { useState, useEffect, useCallback } from 'react';
import { Upload, Trash2, RefreshCw, FileText, AlertCircle, CheckCircle, Clock, Loader } from 'lucide-react';
import { api, type Doc } from '../api/client';
import { useAuth } from '../context/AuthContext';

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending:    <Clock size={13} color="var(--amber)" />,
  processing: <Loader size={13} color="var(--sky)" className="spin" />,
  ready:      <CheckCircle size={13} color="var(--emerald)" />,
  failed:     <AlertCircle size={13} color="var(--rose)" />,
};
const EXT_ICON: Record<string, string> = { pdf: '📄', docx: '📝', txt: '📋', md: '📋' };

function docIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return EXT_ICON[ext] ?? '📁';
}

export default function KnowledgeBaseView() {
  const { org } = useAuth();
  const [docs, setDocs]         = useState<Doc[]>([]);
  const [loading, setLoading]   = useState(false);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError]       = useState('');
  const [success, setSuccess]   = useState('');

  const loadDocs = useCallback(async () => {
    if (!org) return;
    setLoading(true);
    try { setDocs(await api.docs.list(org.id)); }
    catch (e: unknown) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [org]);

  useEffect(() => { loadDocs(); }, [loadDocs]);

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0 || !org) return;
    setUploading(true); setError(''); setSuccess('');
    const results = await Promise.allSettled([...files].map(f => api.docs.upload(org.id, f)));
    const failed = results.filter(r => r.status === 'rejected').length;
    if (failed > 0) setError(`${failed} file(s) failed to upload.`);
    else setSuccess(`${files.length} file(s) uploaded successfully!`);
    await loadDocs();
    setUploading(false);
  }

  async function handleDelete(docId: string) {
    if (!org || !confirm('Delete this document and all its chunks?')) return;
    try { await api.docs.delete(org.id, docId); setDocs(d => d.filter(x => x.id !== docId)); }
    catch (e: unknown) { setError((e as Error).message); }
  }

  async function handleReprocess(docId: string) {
    if (!org) return;
    try {
      const updated = await api.docs.reprocess(org.id, docId);
      setDocs(d => d.map(x => x.id === docId ? updated : x));
    } catch (e: unknown) { setError((e as Error).message); }
  }

  return (
    <div className="flex-col" style={{ height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Knowledge Base</h1>
          <p className="page-subtitle">{docs.length} document{docs.length !== 1 ? 's' : ''} · {docs.filter(d => d.status === 'ready').length} indexed</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={loadDocs} disabled={loading}>
          <RefreshCw size={13} style={loading ? { animation: 'spin 0.7s linear infinite' } : {}} /> Refresh
        </button>
      </div>

      <div className="page-body">
        {error   && <div className="glass-card" style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', color: 'var(--rose)', padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>{error}</div>}
        {success && <div className="glass-card" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', color: 'var(--emerald)', padding: '10px 14px', fontSize: 13, marginBottom: 16 }}>{success}</div>}

        {/* Dropzone */}
        <div
          id="kb-dropzone"
          className={`dropzone ${dragging ? 'dragging' : ''}`}
          style={{ marginBottom: 24 }}
          onClick={() => document.getElementById('kb-file-input')?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleUpload(e.dataTransfer.files); }}
        >
          <input id="kb-file-input" type="file" multiple accept=".pdf,.docx,.txt,.md" style={{ display: 'none' }}
            onChange={e => handleUpload(e.target.files)} />
          {uploading ? (
            <><div className="dropzone-icon"><span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} /></div><div className="dropzone-text">Uploading…</div></>
          ) : (
            <><div className="dropzone-icon"><Upload size={36} /></div>
            <div className="dropzone-text">Drop files here or click to upload</div>
            <div className="dropzone-sub">PDF, DOCX, TXT, MD · Multiple files supported</div></>
          )}
        </div>

        {/* Table */}
        <div className="glass-card" style={{ overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <div className="spinner" style={{ margin: '0 auto 12px', width: 24, height: 24 }} />
              Loading documents…
            </div>
          ) : docs.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center' }}>
              <FileText size={40} style={{ opacity: 0.2, margin: '0 auto 12px', display: 'block' }} />
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>No documents yet</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Upload your first document above to get started</div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Version</th>
                  <th>Uploaded</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {docs.map(doc => (
                  <tr key={doc.id}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 20 }}>{docIcon(doc.filename)}</span>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{doc.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{doc.filename}</div>
                        </div>
                      </div>
                    </td>
                    <td><span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{doc.mime_type}</span></td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                        {STATUS_ICON[doc.status]}
                        <span className={`badge badge-${doc.status === 'ready' ? 'ready' : doc.status === 'failed' ? 'failed' : 'pending'}`}>{doc.status}</span>
                      </span>
                    </td>
                    <td><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>v{doc.version}</span></td>
                    <td><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{new Date(doc.created_at).toLocaleDateString()}</span></td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        {doc.status === 'failed' && (
                          <button className="btn btn-secondary btn-sm btn-icon" onClick={() => handleReprocess(doc.id)} title="Reprocess">
                            <RefreshCw size={12} />
                          </button>
                        )}
                        <button className="btn btn-danger btn-sm btn-icon" onClick={() => handleDelete(doc.id)} title="Delete">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
