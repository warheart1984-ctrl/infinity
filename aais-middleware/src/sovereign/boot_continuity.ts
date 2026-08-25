/**
 * Ring 3 consumer — boot continuity for the middleware.
 *
 * On startup the middleware fetches GET /sovereign/epoch from the
 * enforcement stack and compares it against the last epoch it operated
 * under.
 *
 *   first_boot   no prior epoch observed by this instance
 *   continuous   epoch unchanged since last observation
 *   recovered    epoch changed AND the ledger records a lawful
 *                TRUST_DISCONTINUITY / RECOVERY
 *   needs_auth   epoch changed WITHOUT that record: history cannot be
 *                accounted for, so adapters must not operate until an
 *                operator explicitly accepts the new epoch.
 *
 * Read-only over HTTP (/sovereign/* GET surface); holds no mutation
 * capability (Ring 2).
 */

export interface EpochSnapshot {
  /** Wire format matches GET /sovereign/epoch (snake_case). */
  epoch_id: string | null;
  ledger_head_hash?: string | null;
  chain_intact?: boolean;
}

export interface ContinuityProbe {
  /** True only when TRUST_DISCONTINUITY / RECOVERY evidence was actually seen. */
  discontinuityRecorded: boolean;
}

export type ContinuityStatus = "first_boot" | "continuous" | "recovered" | "needs_auth";

export interface BootContinuityVerdict {
  status: ContinuityStatus;
  reasonCode:
    | "FIRST_BOOT"
    | "EPOCH_UNCHANGED"
    | "EPOCH_RECOVERED_AFTER_DISCONTINUITY"
    | "EPOCH_CHANGED_NO_DISCONTINUITY";
  previousEpochId: string | null;
  currentEpochId: string | null;
  detail: string;
}

export function assessBootContinuity(
  lastSeen: EpochSnapshot | null,
  current: EpochSnapshot,
  probe: ContinuityProbe = { discontinuityRecorded: false },
): BootContinuityVerdict {
  const currentId = current.epoch_id ?? null;
  if (!lastSeen || !lastSeen.epoch_id) {
    return {
      status: "first_boot",
      reasonCode: "FIRST_BOOT",
      previousEpochId: lastSeen?.epoch_id ?? null,
      currentEpochId: currentId,
      detail: "no prior epoch observed by this middleware instance",
    };
  }
  if (lastSeen.epoch_id === currentId) {
    return {
      status: "continuous",
      reasonCode: "EPOCH_UNCHANGED",
      previousEpochId: lastSeen.epoch_id,
      currentEpochId: currentId,
      detail: `epoch ${currentId} matches last-seen`,
    };
  }
  if (probe.discontinuityRecorded) {
    return {
      status: "recovered",
      reasonCode: "EPOCH_RECOVERED_AFTER_DISCONTINUITY",
      previousEpochId: lastSeen.epoch_id,
      currentEpochId: currentId,
      detail:
        "epoch changed but the ledger records a lawful trust discontinuity + recovery",
    };
  }
  return {
    status: "needs_auth",
    reasonCode: "EPOCH_CHANGED_NO_DISCONTINUITY",
    previousEpochId: lastSeen.epoch_id,
    currentEpochId: currentId,
    detail:
      `epoch changed ${lastSeen.epoch_id} -> ${currentId} without a ` +
      "TRUST_DISCONTINUITY record — operator re-baseline required before live traffic",
  };
}

/** Fetch + normalize one snapshot from the enforcement stack. */
export async function fetchEpochSnapshot(
  baseUrl: string,
  fetchImpl: typeof fetch = fetch,
): Promise<EpochSnapshot & Record<string, unknown>> {
  const response = await fetchImpl(`${baseUrl.replace(/\/$/, "")}/sovereign/epoch`);
  if (!response.ok) {
    throw new Error(`sovereign epoch fetch failed: HTTP ${response.status}`);
  }
  const body = (await response.json()) as Record<string, unknown>;
  return {
    epoch_id: (body["epoch_id"] as string | undefined) ?? null,
    ledger_head_hash: (body["ledger_head_hash"] as string | undefined) ?? null,
    ...body,
  };
}

/**
 * Look for discontinuity evidence between epochs via the read-only verdict
 * feed. Absence of evidence is NOT evidence of recovery: callers decide on
 * what they actually saw.
 */
export async function probeDiscontinuity(
  baseUrl: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ContinuityProbe> {
  try {
    const response = await fetchImpl(
      `${baseUrl.replace(/\/$/, "")}/sovereign/verdicts?limit=200`,
    );
    if (!response.ok) return { discontinuityRecorded: false };
    const body = (await response.json()) as {
      verdicts?: Array<{ action?: string; reasonCode?: string }>;
    };
    const hit = (body.verdicts ?? []).find(
      (v) =>
        v.reasonCode === "TRUST_DISCONTINUITY" || v.action === "TRUST_DISCONTINUITY",
    );
    return { discontinuityRecorded: Boolean(hit) };
  } catch {
    // Cannot verify recovery evidence — treat as absent so the epoch
    // comparison conservatively demands re-auth.
    return { discontinuityRecorded: false };
  }
}

/** Adapter-facing gate: adapters consult this before privileged operations. */
export class BootContinuityGate {
  private verdict: BootContinuityVerdict;
  private lastSeen: EpochSnapshot | null;

  constructor(lastSeen: EpochSnapshot | null = null) {
    this.lastSeen = lastSeen;
    this.verdict = assessBootContinuity(lastSeen, lastSeen ?? { epoch_id: null });
  }

  get status(): ContinuityStatus {
    return this.verdict.status;
  }

  get assessment(): Readonly<BootContinuityVerdict> {
    return this.verdict;
  }

  /**
   * Startup sequence: fetch current epoch, probe for discontinuity evidence
   * when the epoch differs, decide, and remember ONLY after deciding — so a
   * crash mid-boot forces the next startup to re-evaluate the same gap.
   */
  async startup(
    baseUrl: string,
    fetchImpl: typeof fetch = fetch,
  ): Promise<BootContinuityVerdict> {
    const current = await fetchEpochSnapshot(baseUrl, fetchImpl);
    const probe =
      this.lastSeen && this.lastSeen.epoch_id !== current.epoch_id
        ? await probeDiscontinuity(baseUrl, fetchImpl)
        : { discontinuityRecorded: false };
    this.verdict = assessBootContinuity(this.lastSeen, current, probe);
    if (this.verdict.status !== "needs_auth") {
      this.lastSeen = {
        epoch_id: current.epoch_id,
        ledger_head_hash: current.ledger_head_hash,
      };
    }
    return this.verdict;
  }

  /** Operator explicitly accepts whatever epoch is now current. */
  acceptCurrentEpoch(epoch: EpochSnapshot): void {
    this.lastSeen = { epoch_id: epoch.epoch_id, ledger_head_hash: epoch.ledger_head_hash };
    this.verdict = assessBootContinuity(this.lastSeen, { ...epoch });
  }

  /** True when live adapter traffic may proceed. */
  operational(): boolean {
    return this.verdict.status !== "needs_auth";
  }
}
