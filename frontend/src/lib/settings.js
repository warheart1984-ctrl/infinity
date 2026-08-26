const STORAGE_KEY = 'aais_settings_v1';

export const defaultSettings = Object.freeze({
  apiUrl: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/legacy_api',
  platformApiUrl: import.meta.env.VITE_PLATFORM_API_URL || 'http://127.0.0.1:9000',
  theme: 'dark',
  operatorMode: true,
});

export function getSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...defaultSettings };
    return { ...defaultSettings, ...JSON.parse(raw) };
  } catch {
    return { ...defaultSettings };
  }
}

export function saveSettings(next) {
  const merged = { ...getSettings(), ...(next || {}) };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
  return merged;
}

export function resetSettings() {
  localStorage.removeItem(STORAGE_KEY);
  return { ...defaultSettings };
}

export function getApiBaseUrl(settingsOrUrl) {
  if (typeof settingsOrUrl === 'string') return settingsOrUrl.replace(/\/+$/, '');
  return (settingsOrUrl?.apiUrl || defaultSettings.apiUrl).replace(/\/+$/, '');
}

export function getApiBaseUrlCandidates(primary) {
  const url = getApiBaseUrl(primary);
  const candidates = new Set();
  candidates.add(url);
  try {
    const parsed = new URL(url);
    const altPorts = ['8000', '8001', '5000', '8080'];
    for (const port of altPorts) {
      const alt = new URL(url);
      alt.port = port;
      candidates.add(alt.toString().replace(/\/+$/, ''));
    }
    candidates.add(`${parsed.protocol}//${parsed.hostname}`.replace(/\/+$/, ''));
  } catch {}
  return [...candidates].filter(Boolean);
}
