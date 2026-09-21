// API layer. The rest of the app only talks to `api` (see bottom of file).
//   ?mock=1 in the URL swaps in mock.js so the UI can be developed without a backend.
//   <meta name="api-base"> sets the backend origin (empty = same origin).
import { ApiError } from './lib/errors.js';
import { mockApi } from './mock.js';

export { ApiError };

const base = (document.querySelector('meta[name="api-base"]')?.content ?? '').replace(/\/$/, '');

/** FastAPI reports errors as {detail: string | [{msg, loc}]}. Turn either into a sentence. */
function messageFromDetail(detail, fallback) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => `${(d.loc ?? []).slice(1).join('.') || 'request'}: ${d.msg}`).join('; ');
  }
  return fallback;
}

async function request(path, { method = 'GET', body, signal } = {}) {
  let response;
  try {
    response = await fetch(base + path, {
      method,
      signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw new ApiError('Request cancelled', { kind: 'aborted' });
    throw new ApiError('Could not reach the server. Check that it is running and try again.', { kind: 'network' });
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(messageFromDetail(payload?.detail, `Request failed (${response.status})`), { status: response.status });
  }
  return payload;
}

const realApi = {
  isMock: false,
  health: (opts) => request('/health', opts),
  examples: (dataset, limit = 6, opts) => request(`/api/examples?dataset=${encodeURIComponent(dataset)}&limit=${limit}`, opts),
  ask: (payload, opts) => request('/ask', { method: 'POST', body: payload, ...opts }),
  retrieve: (payload, opts) => request('/retrieve', { method: 'POST', body: payload, ...opts }),
  evaluation: (dataset, opts) => request(`/api/evaluation?dataset=${encodeURIComponent(dataset)}`, opts),
};

export const api = new URLSearchParams(location.search).has('mock') ? mockApi : realApi;
