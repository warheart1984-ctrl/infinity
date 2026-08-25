/**
 * Mythic: AAIS task ledger
 * Engineering: AaisTaskStore — durable JSON under .runtime/aais_tasks/
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { randomUUID } from "node:crypto";
import {
  normalizeTask,
  type AaisTask,
  type CreateAaisTaskInput,
  type UpdateAaisTaskInput,
} from "./aais_task_model.js";

export interface AaisTaskStoreOptions {
  /** Absolute or cwd-relative path to tasks.json */
  filePath?: string;
  runtimeRoot?: string;
}

function defaultFilePath(runtimeRoot?: string): string {
  const root = runtimeRoot || process.env.AAIS_RUNTIME_DIR || join(process.cwd(), ".runtime");
  return join(root, "aais_tasks", "tasks.json");
}

export class AaisTaskStore {
  private readonly filePath: string;

  constructor(opts: AaisTaskStoreOptions = {}) {
    this.filePath = opts.filePath || defaultFilePath(opts.runtimeRoot);
  }

  private ensureDir(): void {
    mkdirSync(dirname(this.filePath), { recursive: true });
  }

  private load(): AaisTask[] {
    if (!existsSync(this.filePath)) return [];
    try {
      const raw = JSON.parse(readFileSync(this.filePath, "utf8")) as { tasks?: unknown };
      const list = Array.isArray(raw.tasks) ? raw.tasks : [];
      return list
        .filter((t): t is Record<string, unknown> => t != null && typeof t === "object")
        .map((t) =>
          normalizeTask({
            id: String(t.id || randomUUID()),
            title: String(t.title || "Untitled"),
            description: t.description != null ? String(t.description) : undefined,
            createdAt: t.createdAt != null ? String(t.createdAt) : undefined,
            dueDate: t.dueDate != null ? String(t.dueDate) : undefined,
            status: t.status as AaisTask["status"],
            priority: t.priority as AaisTask["priority"],
            tags: Array.isArray(t.tags) ? t.tags.map(String) : undefined,
            source: t.source as AaisTask["source"],
            graphId: t.graphId != null ? String(t.graphId) : undefined,
            updatedAt: t.updatedAt != null ? String(t.updatedAt) : undefined,
          }),
        );
    } catch {
      return [];
    }
  }

  private save(tasks: AaisTask[]): void {
    this.ensureDir();
    writeFileSync(
      this.filePath,
      JSON.stringify({ updatedAt: new Date().toISOString(), tasks }, null, 2) + "\n",
      "utf8",
    );
  }

  create(input: CreateAaisTaskInput): AaisTask {
    const tasks = this.load();
    const task = normalizeTask({
      id: randomUUID(),
      title: input.title,
      description: input.description,
      dueDate: input.dueDate,
      status: input.status || "notStarted",
      priority: input.priority,
      tags: input.tags,
      source: input.source || "aais",
      graphId: input.graphId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    tasks.push(task);
    this.save(tasks);
    return task;
  }

  list(): AaisTask[] {
    return this.load();
  }

  get(id: string): AaisTask | undefined {
    return this.load().find((t) => t.id === id);
  }

  update(id: string, patch: UpdateAaisTaskInput): AaisTask | undefined {
    const tasks = this.load();
    const idx = tasks.findIndex((t) => t.id === id);
    if (idx < 0) return undefined;
    const cur = tasks[idx]!;
    const next = normalizeTask({
      ...cur,
      title: patch.title ?? cur.title,
      description:
        patch.description !== undefined ? patch.description || undefined : cur.description,
      dueDate:
        patch.dueDate === null
          ? undefined
          : patch.dueDate !== undefined
            ? patch.dueDate
            : cur.dueDate,
      status: patch.status ?? cur.status,
      priority: patch.priority ?? cur.priority,
      tags: patch.tags ?? cur.tags,
      source: patch.source ?? cur.source,
      graphId:
        patch.graphId === null
          ? undefined
          : patch.graphId !== undefined
            ? patch.graphId
            : cur.graphId,
      createdAt: cur.createdAt,
      updatedAt: new Date().toISOString(),
    });
    tasks[idx] = next;
    this.save(tasks);
    return next;
  }
}
