const BASE = '/api/v1';

function getToken() {
  return localStorage.getItem('token');
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json', ...(init.headers as object || {}) };
  if (token) (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {};
  if (token) (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: formData, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  return res.json();
}

// ─── Auth ──────────────────────────────────────────────────────────
export const api = {
  auth: {
    register: (data: { email: string; password: string; name: string; organization_name: string }) =>
      request<{ id: string; email: string; name: string }>('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
    login: (email: string, password: string) => {
      const form = new URLSearchParams({ username: email, password });
      return fetch(`${BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form,
      }).then(r => r.ok ? r.json() : r.json().then((e: { detail: string }) => Promise.reject(new Error(e.detail))));
    },
    me: () => request<{ id: string; email: string; name: string }>('/auth/me'),
  },

  // ─── Organizations ─────────────────────────────────────────────
  orgs: {
    list: () => request<Org[]>('/organizations'),
    members: (orgId: string) => request<Member[]>(`/organizations/${orgId}/members`),
    addMember: (orgId: string, data: { email: string; role: string }) =>
      request(`/organizations/${orgId}/members`, { method: 'POST', body: JSON.stringify(data) }),
  },

  // ─── Knowledge Base ────────────────────────────────────────────
  docs: {
    list: (orgId: string) => request<Doc[]>(`/organizations/${orgId}/documents`),
    upload: (orgId: string, file: File) => {
      const fd = new FormData(); fd.append('file', file);
      return upload<Doc>(`/organizations/${orgId}/documents`, fd);
    },
    delete: (orgId: string, docId: string) =>
      request(`/organizations/${orgId}/documents/${docId}`, { method: 'DELETE' }),
    reprocess: (orgId: string, docId: string) =>
      request<Doc>(`/organizations/${orgId}/documents/${docId}/reprocess`, { method: 'POST' }),
  },

  // ─── AI Config ─────────────────────────────────────────────────
  aiConfig: {
    get: (orgId: string) => request<AIConfig>(`/organizations/${orgId}/ai-config`),
    update: (orgId: string, data: Partial<AIConfig>) =>
      request<AIConfig>(`/organizations/${orgId}/ai-config`, { method: 'PUT', body: JSON.stringify(data) }),
  },

  // ─── Conversations ─────────────────────────────────────────────
  conversations: {
    list: (orgId: string) => request<Conversation[]>(`/organizations/${orgId}/conversations`),
    queue: (orgId: string) => request<Conversation[]>(`/organizations/${orgId}/support-queue`),
    get: (id: string) => request<Conversation>(`/conversations/${id}`),
    messages: (id: string) => request<Message[]>(`/conversations/${id}/messages`),
    notes: (id: string) => request<Note[]>(`/conversations/${id}/notes`),
    addNote: (id: string, content: string) =>
      request<Note>(`/conversations/${id}/notes`, { method: 'POST', body: JSON.stringify({ content }) }),
    reply: (id: string, content: string) =>
      request<Message>(`/conversations/${id}/reply`, { method: 'POST', body: JSON.stringify({ content }) }),
    assign: (id: string) =>
      request<Conversation>(`/conversations/${id}/assign`, { method: 'POST', body: JSON.stringify({}) }),
    suggestReply: (id: string) =>
      request<{ suggested_reply: string; citations: Citation[]; confidence_score: number }>(`/conversations/${id}/suggest-reply`, { method: 'POST' }),
    resolve: (id: string) =>
      request<Conversation>(`/conversations/${id}/resolve`, { method: 'POST' }),
    reopen: (id: string) =>
      request<Conversation>(`/conversations/${id}/reopen`, { method: 'POST' }),
    updateStatus: (id: string, status: string) =>
      request<Conversation>(`/conversations/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  },
};

// ─── Types ──────────────────────────────────────────────────────
export interface Org {
  id: string; name: string; slug: string;
}
export interface Member {
  user: { id: string; email: string; name: string };
  role: string;
  created_at: string;
}
export interface Doc {
  id: string; organization_id: string; name: string; filename: string;
  mime_type: string; status: string; version: number; created_at: string; updated_at: string;
}
export interface AIConfig {
  id: string; organization_id: string; assistant_name: string; company_name: string | null;
  system_prompt: string | null; tone: string; language: string; fallback_message: string;
  confidence_threshold: number; human_escalation_enabled: boolean;
  created_at: string; updated_at: string;
}
export interface Conversation {
  id: string; organization_id: string; customer_id: string | null; assigned_agent_id: string | null;
  status: string; priority: string; channel: string; started_at: string; updated_at: string; closed_at: string | null;
}
export interface Citation {
  document_id: string; document_name: string; chunk_index: number; relevance_score: number;
}
export interface Message {
  id: string; conversation_id: string; sender_type: string; sender_id: string | null;
  content: string; message_type: string;
  message_metadata: { citations?: Citation[]; confidence_score?: number; is_fallback?: boolean } | null;
  created_at: string;
}
export interface Note {
  id: string; conversation_id: string; agent_id: string; content: string; created_at: string;
}
