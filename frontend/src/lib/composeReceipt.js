export const COMPOSE_MODE_LABELS = Object.freeze({
  governed_full: 'Governed full compose',
  super_nova: 'Super Nova compose',
  tiny_nova: 'Tiny Nova compose',
  auto: 'Auto compose',
  legacy: 'Legacy compose',
});

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
}

export function normalizeComposeReceipt(payload) {
  const source = asObject(payload);
  if (!source) return null;
  const candidate =
    asObject(source.compose_receipt) ||
    asObject(source.receipt) ||
    asObject(source.super_nova_compose_receipt) ||
    null;
  const mode = candidate?.mode || source.compose_mode || source.mode || 'auto';
  if (!candidate && !source.compose_receipt && !source.receipt_sha256 && !source.receipts) {
    // Nothing receipt-shaped in this payload.
    return null;
  }
  const base = candidate || source;
  const modeLabel = COMPOSE_MODE_LABELS[mode] || String(mode).replace(/[_-]+/g, ' ');
  return {
    mode,
    mode_label: modeLabel,
    receipt_sha256: base.receipt_sha256 || base.sha256 || '',
    generated_at: base.generated_at || base.created_at || new Date().toISOString(),
    modules: Array.isArray(base.modules) ? base.modules : [],
    citations: Array.isArray(base.citations) ? base.citations : [],
    governance_mode: base.governance_mode || base.default_governance_mode || '',
    summary: summarizeSuperNovaCompose({ ...base, mode }),
  };
}

export function summarizeSuperNovaCompose(receipt) {
  if (!receipt || typeof receipt !== 'object') return '';
  const moduleCount = Array.isArray(receipt.modules) ? receipt.modules.length : 0;
  const citationCount = Array.isArray(receipt.citations) ? receipt.citations.length : 0;
  const mode = COMPOSE_MODE_LABELS[receipt.mode] || receipt.mode || 'compose';
  const sha = receipt.receipt_sha256 ? ` · sha ${String(receipt.receipt_sha256).slice(0, 12)}` : '';
  return `${mode}: ${moduleCount} module${moduleCount === 1 ? '' : 's'}, ${citationCount} citation${citationCount === 1 ? '' : 's'}${sha}`;
}
