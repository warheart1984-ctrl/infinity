export async function captureBrowserSnapshot(path, options = {}) {
  const url = `${window.location.origin}${path.startsWith('/') ? path : `/${path}`}`;
  const snapshot = {
    captured_at: new Date().toISOString(),
    url,
    path,
    title: document.title,
    ready_state: document.readyState,
    overlay_visible: Boolean(document.querySelector('[data-vite-error-overlay], .vite-error-overlay')),
    console_error_count: window.__aaisConsoleErrorCount || 0,
    notes: options.notes || '',
  };
  return snapshot;
}
