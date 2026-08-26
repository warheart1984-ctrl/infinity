const STORAGE_KEY = 'aais_history_v1';
const MAX_ENTRIES = 500;

function readAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(entries) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  return entries;
}

export function getHistoryEntries(filter = {}) {
  let entries = readAll();
  if (filter.type) entries = entries.filter((e) => e.type === filter.type);
  if (filter.search) {
    const q = String(filter.search).toLowerCase();
    entries = entries.filter(
      (e) =>
        String(e.prompt || '').toLowerCase().includes(q) ||
        String(e.output || '').toLowerCase().includes(q),
    );
  }
  if (filter.limit) entries = entries.slice(0, filter.limit);
  return [...entries].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
}

export function addHistoryEntry(entry) {
  const record = {
    id: `hist-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    created_at: entry?.created_at || new Date().toISOString(),
    ...entry,
  };
  writeAll([record, ...readAll()]);
  return record;
}

export function deleteHistoryEntry(id) {
  const next = readAll().filter((e) => e.id !== id);
  writeAll(next);
  return next;
}

export function clearHistoryEntries() {
  writeAll([]);
  return [];
}
