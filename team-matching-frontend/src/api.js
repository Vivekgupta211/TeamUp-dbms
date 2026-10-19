const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/$/, '');
export async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const key = import.meta.env.VITE_API_KEY;
  if (key) headers['X-API-Key'] = key;
  let response;
  try { response = await fetch(`${BASE}${path}`, { ...options, headers }); }
  catch { throw new Error(`Cannot reach backend at ${BASE}. Start your FastAPI backend and check its URL.`); }
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!response.ok) throw new Error(data?.error?.message || data?.detail || `Request failed (${response.status})`);
  return data;
}
export const get = (p) => api(p);
export const post = (p, body) => api(p, { method:'POST', body:JSON.stringify(body) });
export const patch = (p, body) => api(p, { method:'PATCH', body:JSON.stringify(body) });
export const put = (p, body) => api(p, { method:'PUT', body:JSON.stringify(body) });
export const del = (p) => api(p, { method:'DELETE' });
