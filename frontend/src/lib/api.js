import { getApiBaseUrl, getSettings } from './settings';

function resolveBase(explicit) {
  if (explicit) return String(explicit).replace(/\/+$/, '');
  try {
    return getApiBaseUrl(getSettings());
  } catch {
    return (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/legacy_api').replace(/\/+$/, '');
  }
}

function buildUrl(path, params, explicitBase) {
  const base = resolveBase(explicitBase);
  let url = `${base}${path.startsWith('/') ? path : `/${path}`}`;
  if (params && typeof params === 'object') {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) qs.append(k, String(v));
    }
    const q = qs.toString();
    if (q) url += `${url.includes('?') ? '&' : '?'}${q}`;
  }
  return url;
}

async function parseBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function request(method, path, options = {}) {
  const { params, body, headers, signal, timeoutMs } = options;
  const controller = new AbortController();
  const timer = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;
  if (signal) signal.addEventListener('abort', () => controller.abort());

  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  try {
    const response = await fetch(buildUrl(path, params, options.base), {
      method,
      headers: isForm ? headers : { 'Content-Type': 'application/json', ...(headers || {}) },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await parseBody(response);
    if (!response.ok) {
      const message =
        (data && typeof data === 'object' && (data.error || data.detail || data.message)) ||
        typeof data === 'string' && data ||
        `Request failed (${response.status})`;
      const err = new Error(typeof message === 'string' ? message : JSON.stringify(message));
      err.status = response.status;
      err.data = data;
      throw err;
    }
    return { data, status: response.status, ok: true };
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export function apiGet(path, options = {}) {
  return request('GET', path, options);
}
export function apiPost(path, body, options = {}) {
  return request('POST', path, { ...options, body });
}
export function apiPut(path, body, options = {}) {
  return request('PUT', path, { ...options, body });
}
export function apiPatch(path, body, options = {}) {
  return request('PATCH', path, { ...options, body });
}
export function apiDelete(path, options = {}) {
  return request('DELETE', path, options);
}

export async function apiPostStream(path, body, handlers = {}, options = {}) {
  const onToken = typeof handlers === 'function' ? handlers : handlers.onToken;
  const base = resolveBase(options.base);
  const url = buildUrl(path, undefined, options.base);
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok || !response.body) {
    const data = await parseBody(response);
    throw new Error((data && data.error) || `Stream failed (${response.status})`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let full = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunkText = decoder.decode(value, { stream: true });
    full += chunkText;
    for (const line of chunkText.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) continue;
      const payload = trimmed.slice(5).trim();
      if (payload === '[DONE]') continue;
      try {
        const parsed = JSON.parse(payload);
        const delta =
          parsed.choices?.[0]?.delta?.content ||
          parsed.delta?.content ||
          parsed.token ||
          parsed.content ||
          '';
        if (delta && onToken) onToken(delta);
      } catch {
        if (onToken) onToken(payload);
      }
    }
    if (onToken && chunkText && !chunkText.includes('data:')) onToken(chunkText);
  }
  return full;
}

export function getApiErrorMessage(error) {
  if (!error) return 'Unknown error';
  if (typeof error === 'string') return error;
  if (error.name === 'AbortError' || /aborted/i.test(error.message || '')) return 'Request timed out';
  return error.message || 'Request failed';
}
