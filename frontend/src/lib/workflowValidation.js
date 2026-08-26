const ALLOWED_EDGE_KINDS = new Set(['sequence', 'branch', 'loop', 'approval', 'fallback']);

export function validateProposedEdge({ nodes = [], edges = [], connection }) {
  if (!connection || !connection.source || !connection.target) {
    return { valid: false, reason: 'Connection missing source or target.' };
  }
  if (connection.source === connection.target) {
    return { valid: false, reason: 'Self-edges are not allowed.' };
  }
  const sourceNode = nodes.find((n) => n.id === connection.source);
  const targetNode = nodes.find((n) => n.id === connection.target);
  if (!sourceNode || !targetNode) return { valid: false, reason: 'Unknown node in connection.' };
  const duplicate = edges.some(
    (e) => e.source === connection.source && e.target === connection.target && !e.targetHandle,
  );
  if (duplicate) return { valid: false, reason: 'An equivalent edge already exists.' };
  const kind = connection.data?.kind || connection.kind || 'sequence';
  if (!ALLOWED_EDGE_KINDS.has(kind)) return { valid: false, reason: `Unknown edge kind "${kind}".` };
  return { valid: true, edge: { id: `${connection.source}->${connection.target}`, source: connection.source, target: connection.target, kind } };
}

export function validateAndBuildWorkflowPayload({ name, description, nodes, edges, metadata } = {}) {
  const failures = [];
  if (!name || !String(name).trim()) failures.push('Workflow name is required.');
  if (!Array.isArray(nodes) || nodes.length === 0) failures.push('At least one node is required.');
  for (const edge of edges || []) {
    if (!edge.source || !edge.target) failures.push(`Edge ${edge.id || '(unnamed)'} is missing endpoints.`);
  }
  if (failures.length) return { valid: false, failures, payload: null };

  return {
    valid: true,
    failures: [],
    payload: {
      name: String(name).trim(),
      description: String(description || '').trim(),
      graph: {
        nodes: nodes.map((n) => ({ id: n.id, kind: n.type || n.kind || 'step', label: n.data?.label || n.label || n.id, config: n.data?.config || {} })),
        edges: (edges || []).map((e) => ({ id: e.id, source: e.source, target: e.target, kind: e.kind || 'sequence' })),
      },
      metadata: metadata || {},
    },
  };
}
