/**
 * Trace store interfaces
 */
export interface ProviderCallEvent {
  id: string;
  requestId: string;
  provider: string;
  lane: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string;
  timestamp: string;
}

export interface EvidenceRecord {
  id: string;
  requestId: string;
  provider: string;
  justification: string;
  /** CEN receipt hash when this evidence was admitted through /sovereign/gate */
  cenReceiptHash?: string;
  metadata?: Record<string, unknown>;
}

export interface ReplayTrace {
  requestId: string;
  traceId?: string;
  events: ProviderCallEvent[];
  evidence: EvidenceRecord[];
  decisionEvents?: Record<string, unknown>[];
}

export interface OrchestratorResult {
  ok: boolean;
  requestId: string;
  traceId: string;
  intent: Record<string, unknown>;
  policy: Record<string, unknown>;
  authority: Record<string, unknown>;
  lanePlan: Record<string, unknown>[];
  outputs: {
    tasks?: Record<string, unknown>[];
    skills?: Record<string, unknown>[];
    pictures?: Record<string, unknown>[];
    taskFlow?: Record<string, unknown>;
  };
  trace: ReplayTrace;
  reasonCodes: string[];
  adaptive?: Record<string, unknown>;
  deepLinks: Record<string, string>;
}
