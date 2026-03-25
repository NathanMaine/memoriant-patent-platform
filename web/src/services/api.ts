const API_BASE = '/api';

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  search: (body: unknown) => fetchAPI('/search', { method: 'POST', body: JSON.stringify(body) }),
  analyze: (body: unknown) => fetchAPI('/analyze', { method: 'POST', body: JSON.stringify(body) }),
  draft: (body: unknown) => fetchAPI('/draft', { method: 'POST', body: JSON.stringify(body) }),
  pipeline: (body: unknown) => fetchAPI('/pipeline', { method: 'POST', body: JSON.stringify(body) }),
  getConfig: () => fetchAPI('/config'),
  updateConfig: (body: unknown) => fetchAPI('/config', { method: 'PUT', body: JSON.stringify(body) }),
  health: () => fetchAPI('/health'),
};
