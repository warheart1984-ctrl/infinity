/**
 * Mythic: Evidence seal store
 * Engineering: EvidenceStore + singleton evidenceStore
 */
import { createHash, randomUUID } from "node:crypto";
import type { EvidenceRecord, ReplayTrace } from "./interfaces.js";

export class EvidenceStore {
  private records: EvidenceRecord[] = [];

  seal(
    partial: Omit<EvidenceRecord, "id"> & { id?: string },
    trace?: ReplayTrace,
  ): EvidenceRecord {
    const material = JSON.stringify({
      requestId: partial.requestId,
      provider: partial.provider,
      justification: partial.justification,
      metadata: partial.metadata ?? {},
    });
    const digest = createHash("sha3-256").update(material).digest("hex");
    const record: EvidenceRecord = {
      id: partial.id ?? `evidence:${digest.slice(0, 32)}`,
      requestId: partial.requestId,
      provider: partial.provider,
      justification: partial.justification,
      metadata: {
        ...(partial.metadata ?? {}),
        sealedAt: new Date().toISOString(),
        nonce: randomUUID().slice(0, 8),
      },
    };
    this.records.push(record);
    if (trace) {
      trace.evidence.push(record);
    }
    return record;
  }

  /** Operator alias for seal */
  record(
    partial: Omit<EvidenceRecord, "id"> & { id?: string },
    trace?: ReplayTrace,
  ): EvidenceRecord {
    return this.seal(partial, trace);
  }

  all(): EvidenceRecord[] {
    return [...this.records];
  }

  clear(): void {
    this.records = [];
  }
}

export const evidenceStore = new EvidenceStore();
