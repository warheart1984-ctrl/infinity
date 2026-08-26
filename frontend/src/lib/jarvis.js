const SESSION_KEY = 'aais_jarvis_session_id';
const DRAFT_KEY = 'aais_jarvis_pending_draft';
const PROFILE_KEY = 'aais_jarvis_profile';

export const SMALL_NOVA_PERSONA_MODE = 'small_nova';
export const TINY_NOVA_PERSONA_MODE = 'tiny_nova';
export const SMALL_NOVA_RESPONSE_MODE = 'small';
export const TINY_NOVA_RESPONSE_MODE = 'tiny';
export const SMALL_NOVA_SYSTEM_PROMPT = 'You are a small nova assistant - calm, grounded, and companion-led with a little more depth.';
export const TINY_NOVA_SYSTEM_PROMPT = 'You are a tiny nova assistant - minimal, warm, and present-focused with one insight at a time.';
export const SUPER_NOVA_PERSONA_MODE = 'super_nova';
export const SUPER_NOVA_RESPONSE_MODE = 'super';
export const SUPER_NOVA_SYSTEM_PROMPT = 'You are a super nova assistant - fully capable and knowledgeable.';
export const TINY_NOVA_ASSISTANT_NAME = 'TinyNova';
export const SMALL_NOVA_ASSISTANT_NAME = 'SmallNova';
export const SUPER_NOVA_ASSISTANT_NAME = 'SuperNova';

let storedProfile = {};

export function getActiveJarvisSessionId() {
  try {
    return localStorage.getItem(SESSION_KEY) || '';
  } catch {
    return '';
  }
}

export function setActiveJarvisSessionId(sessionId) {
  try {
    if (sessionId) localStorage.setItem(SESSION_KEY, sessionId);
    else localStorage.removeItem(SESSION_KEY);
  } catch {}
  return sessionId || '';
}

export function setPendingJarvisDraft(draft) {
  try {
    if (draft) localStorage.setItem(DRAFT_KEY, typeof draft === 'string' ? draft : JSON.stringify(draft));
    else localStorage.removeItem(DRAFT_KEY);
  } catch {}
  return draft || '';
}

export function consumePendingJarvisDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    localStorage.removeItem(DRAFT_KEY);
    if (!raw) return '';
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  } catch {
    return '';
  }
}

export function getJarvisProfile() {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function saveJarvisProfile(profile) {
  try {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    storedProfile = profile;
    return profile;
  } catch {
    return {};
  }
}

export function clearActiveJarvisSessionId() {
  try {
    localStorage.removeItem(SESSION_KEY);
    return '';
  } catch {
    return '';
  }
}

export function applyPersonaProfileSelection(profile, personaMode) {
  const nextProfile = { ...profile };
  if (personaMode === 'small_nova') {
    nextProfile.personaMode = 'small_nova';
    nextProfile.systemPrompt = 'You are a small nova assistant - calm, grounded, and companion-led with a little more depth.';
  } else if (personaMode === 'tiny_nova') {
    nextProfile.personaMode = 'tiny_nova';
    nextProfile.systemPrompt = 'You are a tiny nova assistant - minimal, warm, and present-focused with one insight at a time.';
  } else if (personaMode === 'builder') {
    nextProfile.personaMode = 'builder';
    nextProfile.systemPrompt = 'Ship fast with practical next steps.';
  } else if (personaMode === 'sharp') {
    nextProfile.personaMode = 'sharp';
    nextProfile.systemPrompt = 'Be blunt, crisp, and highly opinionated.';
  } else if (personaMode === 'research') {
    nextProfile.personaMode = 'research';
    nextProfile.systemPrompt = 'Lean on evidence, comparisons, and uncertainty.';
  } else if (personaMode === 'unfiltered') {
    nextProfile.personaMode = 'unfiltered';
    nextProfile.systemPrompt = 'Stay direct and candid without losing judgment.';
  }
  return nextProfile;
}

export function applyRuntimeProfileSelection(profile, payload) {
  const nextProfile = { ...profile };
  if (payload.preferred_mode) {
    nextProfile.personaMode = payload.preferred_mode;
  }
  if (payload.system_prompt) {
    nextProfile.systemPrompt = payload.system_prompt;
  }
  if (payload.response_mode) {
    nextProfile.responseMode = payload.response_mode;
  }
  if (payload.provider) {
    nextProfile.preferredProvider = payload.provider;
  }
  return nextProfile;
}

export function applyResponseModeProfileSelection(profile, modeId) {
  const nextProfile = { ...profile };
  const modeLabel = modeId ? modeId.replace(/_/g, ' ') : 'Fast';
  nextProfile.responseMode = modeLabel;
  return nextProfile;
}

export function mapSessionRuntime(sessionId) {
  return { sessionId, status: 'active', timestamp: new Date().toISOString() };
}

export function mapSessionTurns(turns) {
  return turns.map((turn, index) => ({
    id: index,
    role: turn.role,
    content: turn.content,
  }));
}

export function resolveOperatingModeDisplay(modeId) {
  const modeMap = {
    small: 'Small',
    tiny: 'Tiny',
    fast: 'Fast',
    think: 'Think',
    debug: 'Debug',
    builder: 'Builder',
    research: 'Research',
    operator: 'Operator',
  };
  return modeMap[modeId] || (modeId ? modeId.replace(/_/g, ' ') : 'Fast');
}