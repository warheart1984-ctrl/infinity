/**
 * Auth availability flag. Amplify Cognito auth is considered enabled only when
 * a real amplify_outputs.json config exists (see src/amplify_outputs.json.example).
 */

const amplifyConfigModules = import.meta.glob('../amplify_outputs.json', {
  eager: true,
});

export function isAmplifyAuthEnabled() {
  const hasConfig = Object.keys(amplifyConfigModules).length > 0;
  const flag = String(import.meta.env.VITE_AMPLIFY_AUTH_ENABLED || '').toLowerCase();
  if (flag === '1' || flag === 'true') return hasConfig;
  return hasConfig;
}

export function getAmplifyAuthConfig() {
  const keys = Object.keys(amplifyConfigModules);
  return keys.length ? amplificationSafe(keys[0]) : null;
}

function amplificationSafe(key) {
  return amplifyConfigModules[key]?.default ?? null;
}
