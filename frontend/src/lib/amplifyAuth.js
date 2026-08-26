/**
 * Amplify Cognito session bridge.
 *
 * Every call degrades gracefully when auth is disabled or aws-amplify cannot
 * load: the operator console must remain usable in local / offline mode.
 */

import { getAmplifyAuthConfig, isAmplifyAuthEnabled } from './auth';

let amplifyMod = null;
let initAttempted = false;
let initOk = false;
let cachedToken = '';

async function loadAmplify() {
  if (amplifyMod) return amplifyMod;
  if (!isAmplifyAuthEnabled() || !getAmplifyAuthConfig()) return null;
  try {
    amplifyMod = await import('aws-amplify');
    const { Amplify } = amplifyMod;
    Amplify.configure(getAmplifyAuthConfig());
    return amplifyMod;
  } catch {
    return null;
  }
}

export async function initAmplifyAuth() {
  if (initAttempted) return initOk;
  initAttempted = true;
  const mod = await loadAmplify();
  if (!mod) {
    initOk = false;
    return initOk;
  }
  try {
    const user = await mod.getCurrentUser();
    initOk = Boolean(user);
  } catch {
    initOk = false;
  }
  return initOk;
}

export function isAmplifyAuthActive() {
  return isAmplifyAuthEnabled() && initOk;
}

export async function ensureAmplifySession() {
  if (!isAmplifyAuthEnabled()) return '';
  const mod = await loadAmplify();
  if (!mod) return '';
  try {
    const session = await mod.fetchAuthSession();
    const token = session?.tokens?.idToken?.toString() || session?.tokens?.accessToken?.toString() || '';
    cachedToken = token;
    initOk = Boolean(token);
    return token;
  } catch {
    initOk = false;
    return cachedToken && !initAttempted ? cachedToken : '';
  }
}

export async function refreshAmplifySession() {
  const mod = await loadAmplify();
  if (!mod) return false;
  try {
    await mod.fetchAuthSession({ forceRefresh: true });
    return true;
  } catch {
    return false;
  }
}

export async function signOutAmplify() {
  const mod = await loadAmplify();
  if (!mod) return;
  try {
    await mod.signOut();
  } catch {}
  cachedToken = '';
  initOk = false;
  initAttempted = false;
}

export function teardownAmplifyAuth() {
  cachedToken = '';
  initOk = false;
  initAttempted = false;
}
