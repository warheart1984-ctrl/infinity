/**
 * Mythic: AAIS Tasks lane
 * Engineering: AaisTasksAdapter — primary task artifact (no Graph token required)
 */
import type { AdapterResult } from "../intent_bus/interfaces.js";
import type { AaisTask, CreateAaisTaskInput, TaskStatus } from "./aais_task_model.js";
import { AaisTaskStore } from "./aais_task_store.js";

export interface AaisTasksAdapterConfig {
  store?: AaisTaskStore;
  runtimeRoot?: string;
}

export class AaisTasksAdapter {
  readonly provider = "aais_tasks";
  readonly lane = "aais_tasks";
  private readonly store: AaisTaskStore;

  constructor(config: AaisTasksAdapterConfig = {}) {
    this.store = config.store || new AaisTaskStore({ runtimeRoot: config.runtimeRoot });
  }

  createTask(input: CreateAaisTaskInput): AdapterResult {
    const task = this.store.create(input);
    return {
      provider: this.provider,
      lane: this.lane,
      status: "ok",
      ok: true,
      justification: `AAIS task created: ${task.title}`,
      reasonCode: "AAIS_TASK_CREATED",
      output: { task },
    };
  }

  listTasks(): AdapterResult {
    const tasks = this.store.list();
    return {
      provider: this.provider,
      lane: this.lane,
      status: "ok",
      ok: true,
      justification: `Listed ${tasks.length} AAIS tasks`,
      reasonCode: "AAIS_TASK_LIST",
      output: { tasks },
    };
  }

  updateTask(id: string, patch: { title?: string; status?: TaskStatus; dueDate?: string }): AdapterResult {
    const task = this.store.update(id, patch);
    if (!task) {
      return {
        provider: this.provider,
        lane: this.lane,
        status: "error",
        ok: false,
        justification: `Task not found: ${id}`,
        reasonCode: "AAIS_TASK_NOT_FOUND",
      };
    }
    return {
      provider: this.provider,
      lane: this.lane,
      status: "ok",
      ok: true,
      justification: `AAIS task updated: ${task.id}`,
      reasonCode: "AAIS_TASK_UPDATED",
      output: { task },
    };
  }

  updateStatus(id: string, status: TaskStatus): AdapterResult {
    return this.updateTask(id, { status });
  }

  getStore(): AaisTaskStore {
    return this.store;
  }

  /** Convenience for orchestrator */
  createFromTitle(title: string, extra?: Partial<CreateAaisTaskInput>): AaisTask {
    return this.store.create({ title, ...extra, source: extra?.source || "aais" });
  }
}
