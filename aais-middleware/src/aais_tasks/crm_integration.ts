/**
 * Mythic: CRM follow-up from AAIS task
 * Engineering: createFollowUpFromTask
 */
import type { AaisTask } from "./aais_task_model.js";
import type { CrmAdapter } from "../provider_adapters/crm_adapter.js";

export interface CrmFollowUpResult {
  ok: boolean;
  reasonCode: string;
  skipped?: boolean;
  skipReason?: string;
  dealId?: string;
  noteId?: string;
  error?: string;
}

export async function createFollowUpFromTask(
  crm: CrmAdapter,
  task: AaisTask,
  leadId?: string,
): Promise<CrmFollowUpResult> {
  const tags = (task.tags || []).map((t) => t.toLowerCase());
  const wantsCrm = Boolean(leadId) || tags.includes("crm");
  if (!wantsCrm) {
    return {
      ok: true,
      skipped: true,
      skipReason: "no crm leadId/tag",
      reasonCode: "CRM_FOLLOWUP_SKIPPED",
    };
  }
  if (!crm.isConnected()) {
    return {
      ok: false,
      skipped: true,
      skipReason: "CRM not connected",
      reasonCode: "CRM_NOT_CONNECTED",
      error: "CRM store unavailable or disconnected",
    };
  }
  const follow = await crm.createFollowUp(task, leadId || task.id);
  return {
    ok: Boolean(follow.ok),
    reasonCode: String(follow.reasonCode || "CRM_FOLLOWUP"),
    dealId: follow.dealId != null ? String(follow.dealId) : undefined,
    noteId: follow.noteId != null ? String(follow.noteId) : undefined,
    error: follow.error != null ? String(follow.error) : undefined,
  };
}
