/**
 * Mythic: CRM subcontract
 * Engineering: CrmAdapter — local durable store + optional HTTP endpoint
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { randomUUID } from "node:crypto";
import type { AaisTask } from "../aais_tasks/aais_task_model.js";
import type { AdapterResult } from "../intent_bus/interfaces.js";

export interface CrmConfig {
  endpoint?: string;
  apiKey?: string;
  filePath?: string;
  runtimeRoot?: string;
  connected?: boolean;
  fetchImpl?: typeof fetch;
}

export interface CrmLead {
  id: string;
  name: string;
  email?: string;
  company?: string;
  status: string;
  createdAt: string;
  updatedAt?: string;
}

export interface CrmDeal {
  id: string;
  leadId: string;
  title: string;
  stage: string;
  notes: { id: string; text: string; createdAt: string }[];
  nextAction?: string;
  probability?: number;
  source?: string;
  createdAt: string;
  updatedAt?: string;
}

interface CrmDb {
  leads: CrmLead[];
  deals: CrmDeal[];
  connected: boolean;
}

function defaultPath(runtimeRoot?: string): string {
  const root = runtimeRoot || process.env.AAIS_RUNTIME_DIR || join(process.cwd(), ".runtime");
  return join(root, "crm", "store.json");
}

export class CrmAdapter {
  readonly provider = "crm";
  readonly lane = "crm";
  private readonly config: CrmConfig;
  private readonly filePath: string;

  constructor(config: CrmConfig = {}) {
    this.config = config;
    this.filePath = config.filePath || defaultPath(config.runtimeRoot);
  }

  isConnected(): boolean {
    if (this.config.connected === false) return false;
    if (this.config.endpoint) return true;
    return true; // local durable CRM is always available for MVP
  }

  private load(): CrmDb {
    if (!existsSync(this.filePath)) {
      return { leads: [], deals: [], connected: true };
    }
    try {
      const raw = JSON.parse(readFileSync(this.filePath, "utf8")) as Partial<CrmDb>;
      return {
        leads: Array.isArray(raw.leads) ? raw.leads : [],
        deals: Array.isArray(raw.deals) ? raw.deals : [],
        connected: raw.connected !== false,
      };
    } catch {
      return { leads: [], deals: [], connected: true };
    }
  }

  private save(db: CrmDb): void {
    mkdirSync(dirname(this.filePath), { recursive: true });
    writeFileSync(
      this.filePath,
      JSON.stringify({ ...db, updatedAt: new Date().toISOString() }, null, 2) + "\n",
      "utf8",
    );
  }

  private async call(path: string, body: unknown): Promise<Response> {
    const endpoint = this.config.endpoint;
    if (!endpoint) {
      throw new Error("CRM endpoint not configured");
    }
    const fetchImpl = this.config.fetchImpl ?? globalThis.fetch;
    return fetchImpl(`${endpoint.replace(/\/$/, "")}/${path.replace(/^\//, "")}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.config.apiKey ? { "X-API-Key": this.config.apiKey } : {}),
      },
      body: JSON.stringify(body),
    });
  }

  async createFollowUp(
    task: AaisTask,
    leadId: string,
  ): Promise<Record<string, unknown>> {
    if (this.config.endpoint) {
      const res = await this.call("deals/create", {
        leadId,
        stage: "follow_up",
        nextAction: task.title,
        probability: 0.5,
        source: task.source ?? "aais",
      });
      if (!res.ok) {
        return {
          ok: false,
          reasonCode: "CRM_HTTP_ERROR",
          status: res.status,
          error: `CRM HTTP ${res.status}`,
        };
      }
      const data = (await res.json()) as Record<string, unknown>;
      return { ok: true, reasonCode: "CRM_FOLLOWUP_CREATED", ...data };
    }

    const db = this.load();
    let lead = db.leads.find((l) => l.id === leadId);
    if (!lead) {
      lead = {
        id: leadId || randomUUID(),
        name: task.title.slice(0, 120),
        status: "follow_up",
        createdAt: new Date().toISOString(),
      };
      db.leads.push(lead);
    }
    const noteId = randomUUID();
    const deal: CrmDeal = {
      id: randomUUID(),
      leadId: lead.id,
      title: `Follow-up: ${task.title}`.slice(0, 200),
      stage: "follow_up",
      nextAction: task.title,
      probability: 0.5,
      source: task.source ?? "aais",
      notes: [
        {
          id: noteId,
          text: `AAIS task ${task.id}: ${task.title}${task.dueDate ? ` due ${task.dueDate}` : ""}`,
          createdAt: new Date().toISOString(),
        },
      ],
      createdAt: new Date().toISOString(),
    };
    db.deals.push(deal);
    this.save(db);
    return {
      ok: true,
      reasonCode: "CRM_FOLLOWUP_CREATED",
      dealId: deal.id,
      leadId: lead.id,
      noteId,
      deal,
    };
  }

  createLead(input: { name: string; email?: string; company?: string }): AdapterResult {
    const db = this.load();
    const lead: CrmLead = {
      id: randomUUID(),
      name: input.name.slice(0, 200),
      email: input.email,
      company: input.company,
      status: "new",
      createdAt: new Date().toISOString(),
    };
    db.leads.push(lead);
    this.save(db);
    return {
      provider: this.provider,
      lane: this.lane,
      status: "ok",
      ok: true,
      justification: `CRM lead created: ${lead.name}`,
      reasonCode: "CRM_LEAD_CREATED",
      output: { lead },
    };
  }

  updateLead(id: string, patch: Partial<CrmLead>): AdapterResult {
    const db = this.load();
    const idx = db.leads.findIndex((l) => l.id === id);
    if (idx < 0) {
      return {
        provider: this.provider,
        lane: this.lane,
        status: "error",
        ok: false,
        justification: "Lead not found",
        reasonCode: "CRM_LEAD_NOT_FOUND",
      };
    }
    const cur = db.leads[idx]!;
    db.leads[idx] = { ...cur, ...patch, id: cur.id, updatedAt: new Date().toISOString() };
    this.save(db);
    return {
      provider: this.provider,
      lane: this.lane,
      status: "ok",
      ok: true,
      justification: "CRM lead updated",
      reasonCode: "CRM_LEAD_UPDATED",
      output: { lead: db.leads[idx] },
    };
  }

  setDealStage(dealId: string, stage: string): AdapterResult {
    const db = this.load();
    const idx = db.deals.findIndex((d) => d.id === dealId);
    if (idx < 0) {
      return {
        provider: this.provider,
        lane: this.lane,
        status: "error",
        ok: false,
        justification: "Deal not found",
        reasonCode: "CRM_DEAL_NOT_FOUND",
      };
    }
    db.deals[idx] = {
      ...db.deals[idx]!,
      stage: stage.slice(0, 80),
      updatedAt: new Date().toISOString(),
    };
    this.save(db);
    return {
      provider: this.provider,
      lane: this.lane,
      status: "ok",
      ok: true,
      justification: `Deal stage → ${stage}`,
      reasonCode: "CRM_DEAL_STAGE",
      output: { deal: db.deals[idx] },
    };
  }

  addDealNote(dealId: string, text: string): AdapterResult {
    const db = this.load();
    const idx = db.deals.findIndex((d) => d.id === dealId);
    if (idx < 0) {
      return {
        provider: this.provider,
        lane: this.lane,
        status: "error",
        ok: false,
        justification: "Deal not found",
        reasonCode: "CRM_DEAL_NOT_FOUND",
      };
    }
    const note = {
      id: randomUUID(),
      text: text.slice(0, 4000),
      createdAt: new Date().toISOString(),
    };
    db.deals[idx]!.notes.push(note);
    db.deals[idx]!.updatedAt = new Date().toISOString();
    this.save(db);
    return {
      provider: this.provider,
      lane: this.lane,
      status: "ok",
      ok: true,
      justification: "CRM note added",
      reasonCode: "CRM_DEAL_NOTE",
      output: { deal: db.deals[idx], note },
    };
  }

  execute(action: string, payload: Record<string, unknown> = {}): AdapterResult {
    switch (action) {
      case "crm.leads.create":
        return this.createLead({
          name: String(payload.name || payload.title || "Lead"),
          email: payload.email != null ? String(payload.email) : undefined,
          company: payload.company != null ? String(payload.company) : undefined,
        });
      case "crm.leads.update":
        return this.updateLead(String(payload.id || payload.leadId || ""), payload as Partial<CrmLead>);
      case "crm.deals.stage":
        return this.setDealStage(
          String(payload.dealId || payload.id || ""),
          String(payload.stage || "open"),
        );
      case "crm.deals.note":
        return this.addDealNote(
          String(payload.dealId || payload.id || ""),
          String(payload.text || payload.note || ""),
        );
      default:
        return {
          provider: this.provider,
          lane: this.lane,
          status: "error",
          ok: false,
          justification: `Unknown CRM action: ${action}`,
          reasonCode: "CRM_UNKNOWN_ACTION",
        };
    }
  }
}
