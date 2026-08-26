const ARCHIVE_KEY = 'aais_nova_session_archives_v1';
const ACTIVE_KEY = 'aais_nova_active_archive';
const PENDING_KEY = 'aais_nova_pending_archive';

function readAll() {
  try {
    const raw = localStorage.getItem(ARCHIVE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(entries) {
  localStorage.setItem(ARCHIVE_KEY, JSON.stringify(entries));
  return entries;
}

export function buildDefaultNovaArchiveTitle(assistantName = 'Nova') {
  const date = new Date().toISOString().slice(0, 16).replace('T', ' ');
  return `${assistantName} Session ${date}`;
}

export async function listNovaSessionArchives(filter = {}) {
  let entries = readAll();
  if (filter.assistantName) {
    entries = entries.filter((e) => e.assistant_name === filter.assistantName);
  }
  return [...entries].sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
}

export function saveNovaSessionArchive(archive) {
  const now = new Date().toISOString();
  const entry = {
    archive_id: archive?.archive_id || `nova-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: archive?.title || buildDefaultNovaArchiveTitle(archive?.assistant_name),
    assistant_name: archive?.assistant_name || 'Nova',
    messages: Array.isArray(archive?.messages) ? archive.messages : [],
    created_at: archive?.created_at || now,
    updated_at: now,
    ...archive,
    updated_at: now,
  };
  const all = readAll();
  const idx = all.findIndex((e) => e.archive_id === entry.archive_id);
  if (idx >= 0) all[idx] = { ...all[idx], ...entry };
  else all.unshift(entry);
  writeAll(all);
  setActiveNovaSessionArchive(entry.archive_id);
  return entry;
}

export async function openNovaSessionArchive(archiveId) {
  const found = readAll().find((e) => e.archive_id === archiveId) || null;
  if (found) setActiveNovaSessionArchive(found.archive_id);
  return found;
}

export function deleteNovaSessionArchive(archiveId) {
  writeAll(readAll().filter((e) => e.archive_id !== archiveId));
  if (getActiveNovaSessionArchive()?.archive_id === archiveId) clearActiveNovaSessionArchive();
}

export function getActiveNovaSessionArchive() {
  try {
    const id = localStorage.getItem(ACTIVE_KEY);
    if (!id) return null;
    return readAll().find((e) => e.archive_id === id) || null;
  } catch {
    return null;
  }
}

export function setActiveNovaSessionArchive(archiveId) {
  try {
    localStorage.setItem(ACTIVE_KEY, archiveId || '');
  } catch {}
  return archiveId || null;
}

export function clearActiveNovaSessionArchive() {
  try {
    localStorage.removeItem(ACTIVE_KEY);
  } catch {}
}

export function setPendingNovaSessionArchive(archive) {
  try {
    if (archive) localStorage.setItem(PENDING_KEY, JSON.stringify(archive));
    else localStorage.removeItem(PENDING_KEY);
  } catch {}
}

export function consumePendingNovaSessionArchive() {
  try {
    const raw = localStorage.getItem(PENDING_KEY);
    localStorage.removeItem(PENDING_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function toLoadedSessionArchivePayload(archive) {
  if (!archive || typeof archive !== 'object') return null;
  return {
    sessionTitle: archive.title || '',
    messages: Array.isArray(archive.messages) ? archive.messages : [],
    assistantName: archive.assistant_name || 'Nova',
    archivedAt: archive.updated_at || archive.created_at || null,
    meta: { source: 'nova_session_archive', archive_id: archive.archive_id },
  };
}
