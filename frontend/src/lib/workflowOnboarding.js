export function buildSeedWorkflowFromOnboarding(onboardingState = {}) {
  const goal = onboardingState.goal || onboardingState.primary_goal || 'Governed automation';
  const steps = Array.isArray(onboardingState.steps) && onboardingState.steps.length
    ? onboardingState.steps
    : ['collect intent', 'gather evidence', 'draft result', 'request approval'];
  return {
    name: `Seed: ${goal}`.slice(0, 80),
    description: `Seeded from operator onboarding (${new Date().toISOString().slice(0, 10)}).`,
    nodes: steps.map((label, i) => ({
      id: `seed_${i + 1}`,
      type: i === steps.length - 1 ? 'approval' : 'step',
      position: { x: 80 + i * 220, y: 120 },
      data: { label },
    })),
    edges: steps.slice(1).map((_, i) => ({
      id: `seed_${i + 1}->seed_${i + 2}`,
      source: `seed_${i + 1}`,
      target: `seed_${i + 2}`,
      kind: 'sequence',
    })),
  };
}

function scoreTemplate(template, answers = {}) {
  let score = 0;
  const haystack = JSON.stringify(template).toLowerCase();
  for (const value of Object.values(answers)) {
    const token = String(value).toLowerCase().trim();
    if (token && haystack.includes(token)) score += 2;
  }
  if (answers.goal && template.name && template.name.toLowerCase().includes(String(answers.goal).toLowerCase())) score += 3;
  return score;
}

export function rankTemplatesForOnboarding(templates = [], answers = {}) {
  return templates
    .map((t) => ({ template: t, score: scoreTemplate(t, answers) }))
    .sort((a, b) => b.score - a.score)
    .map((entry) => entry.template);
}

export function getTopRecommendations(templates = [], answers = {}, limit = 3) {
  return rankTemplatesForOnboarding(templates, answers).slice(0, limit);
}
