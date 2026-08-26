const KEY_STORAGE = 'aais_platform_api_key';

const envBase = String(import.meta.env.VITE_PLATFORM_API_URL || '').replace(/\/+$/, '');

export function getPlatformApiBaseUrl() {
  try {
    const settings = JSON.parse(localStorage.getItem('aais_settings_v1') || '{}');
    if (settings.platformApiUrl) return String(settings.platformApiUrl).replace(/\/+$/, '');
  } catch {}
  return envBase || 'http://127.0.0.1:9000';
}

export function getPlatformApiKey() {
  try {
    return localStorage.getItem(KEY_STORAGE) || import.meta.env.VITE_PLATFORM_API_KEY || '';
  } catch {
    return '';
  }
}

export function setPlatformApiKey(key) {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {}
  return key || '';
}

async function platformRequest(method, path, body) {
  const key = getPlatformApiKey();
  const response = await fetch(`${getPlatformApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { Authorization: `Bearer ${key}`, 'X-Api-Key': key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    throw new Error((data && (data.error || data.detail)) || `Platform request failed (${response.status})`);
  }
  return data;
}

export function platformGet(path) {
  return platformRequest('GET', path);
}
export function platformPost(path, body) {
  return platformRequest('POST', path, body ?? {});
}
export function platformPut(path, body) {
  return platformRequest('PUT', path, body ?? {});
}
