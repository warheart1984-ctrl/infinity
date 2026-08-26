/**
 * Pre-render auth bootstrap. Must ALWAYS resolve so the operator console
 * renders even with no AWS configuration present (local / sovereign mode).
 */

import { initAmplifyAuth } from './amplifyAuth';

let bootstrapped = false;

export async function bootstrapAuth() {
  if (bootstrapped) return;
  try {
    await initAmplifyAuth();
  } catch {
    // Auth is optional; never block the console on it.
  } finally {
    bootstrapped = true;
  }
}

export default bootstrapAuth;
