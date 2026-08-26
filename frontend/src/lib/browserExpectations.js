const TARGETS = [
  { key: 'operator_console', path: '/operator', label: 'Operator Console', expectation: 'Console renders session list, mission board and chat turn controls without console errors.' },
  { key: 'jarvis_console', path: '/jarvis', label: 'Jarvis Console', expectation: 'Chat turn streams a governed reply; approval boundary is stated before any tool execution.' },
  { key: 'dashboard', path: '/', label: 'Dashboard', expectation: 'Health, active model mode and memory digest render from live backend data.' },
  { key: 'workflows', path: '/workflows', label: 'Workflow Builder', expectation: 'Builder canvas loads; proposed edges validate against schema before save.' },
  { key: 'settings', path: '/settings', label: 'Settings', expectation: 'Backend connection check reports Connected with the active model mode.' },
];

export function listBrowserVerificationTargets() {
  return [...TARGETS];
}

export function getBrowserExpectationGuide(path) {
  const target = TARGETS.find((t) => t.path === (path || '').split('?')[0]);
  if (!target) return null;
  return {
    key: target.key,
    label: target.label,
    expectation: target.expectation,
    verification_path: target.path,
  };
}
