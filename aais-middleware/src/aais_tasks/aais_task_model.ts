/**
 * Mythic: AAIS To Do
 * Engineering: AaisTask
 */
export type TaskStatus = "notStarted" | "inProgress" | "completed";
export type TaskPriority = "low" | "normal" | "high";
export type TaskSource = "aais" | "graph" | "crm" | "gmail";

export interface AaisTask {
  id: string;
  title: string;
  description?: string;
  createdAt: string;
  dueDate?: string;
  status: TaskStatus;
  priority?: TaskPriority;
  tags?: string[];
  source?: TaskSource;
  graphId?: string;
  updatedAt?: string;
}

export interface CreateAaisTaskInput {
  title: string;
  description?: string;
  dueDate?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  tags?: string[];
  source?: TaskSource;
  graphId?: string;
}

export interface UpdateAaisTaskInput {
  title?: string;
  description?: string;
  dueDate?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  tags?: string[];
  source?: TaskSource;
  graphId?: string | null;
}

export function isTaskStatus(value: unknown): value is TaskStatus {
  return value === "notStarted" || value === "inProgress" || value === "completed";
}

export function normalizeTask(raw: Partial<AaisTask> & { title: string; id: string }): AaisTask {
  const status = isTaskStatus(raw.status) ? raw.status : "notStarted";
  return {
    id: raw.id,
    title: String(raw.title).slice(0, 500),
    description: raw.description ? String(raw.description).slice(0, 8000) : undefined,
    createdAt: raw.createdAt || new Date().toISOString(),
    dueDate: raw.dueDate || undefined,
    status,
    priority: raw.priority === "low" || raw.priority === "high" ? raw.priority : "normal",
    tags: Array.isArray(raw.tags) ? raw.tags.map(String).slice(0, 32) : undefined,
    source: raw.source || "aais",
    graphId: raw.graphId,
    updatedAt: raw.updatedAt,
  };
}
