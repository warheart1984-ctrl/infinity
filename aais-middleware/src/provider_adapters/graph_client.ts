/**
 * Mythic: Microsoft Graph conduit
 * Engineering: callGraph / GraphClient
 */
export const GRAPH_BASE = "https://graph.microsoft.com/v1.0";

export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface GraphCallResult {
  ok: boolean;
  status: number;
  data?: unknown;
  error?: string;
  reasonCode: string;
  simulated?: boolean;
}

export type FetchLike = (
  input: string | URL,
  init?: { method?: string; headers?: Record<string, string>; body?: string },
) => Promise<{
  ok: boolean;
  status: number;
  text(): Promise<string>;
  json(): Promise<unknown>;
}>;

/** Alias used by GraphTasksAdapter (operator name). */
export async function graphCall(
  token: string | undefined,
  path: string,
  method: HttpMethod = "GET",
  body?: unknown,
  opts?: { fetchImpl?: FetchLike; forceSimulate?: boolean },
): Promise<GraphCallResult> {
  return callGraph(token, path, method, body, opts);
}

export async function callGraph(
  token: string | undefined,
  path: string,
  method: HttpMethod = "GET",
  body?: unknown,
  opts?: { fetchImpl?: FetchLike; forceSimulate?: boolean },
): Promise<GraphCallResult> {
  const cleanPath = path.replace(/^\//, "");
  if (!token || opts?.forceSimulate) {
    return {
      ok: true,
      status: 200,
      simulated: true,
      reasonCode: "GRAPH_SIMULATE",
      data: {
        simulated: true,
        method,
        path: cleanPath,
        body: body ?? null,
      },
    };
  }

  const fetchImpl = opts?.fetchImpl ?? (globalThis.fetch as FetchLike);
  if (!fetchImpl) {
    return {
      ok: false,
      status: 0,
      reasonCode: "GRAPH_NO_FETCH",
      error: "fetch unavailable",
    };
  }

  try {
    const res = await fetchImpl(`${GRAPH_BASE}/${cleanPath}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    let data: unknown = undefined;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { raw: text.slice(0, 2000) };
      }
    }
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        data,
        error: `Graph HTTP ${res.status}`,
        reasonCode: "GRAPH_HTTP_ERROR",
      };
    }
    return {
      ok: true,
      status: res.status,
      data,
      reasonCode: "GRAPH_LIVE_OK",
    };
  } catch (err) {
    return {
      ok: false,
      status: 0,
      error: err instanceof Error ? err.message : String(err),
      reasonCode: "GRAPH_NETWORK_ERROR",
    };
  }
}

/** Tasks → To Do lists */
export async function graphCreateTodoTask(
  token: string | undefined,
  title: string,
  opts?: { fetchImpl?: FetchLike; listId?: string },
): Promise<GraphCallResult> {
  const listId = opts?.listId || "tasks";
  return callGraph(
    token,
    `me/todo/lists/${encodeURIComponent(listId)}/tasks`,
    "POST",
    { title, status: "notStarted" },
    { fetchImpl: opts?.fetchImpl },
  );
}

export async function graphListTodoTasks(
  token: string | undefined,
  opts?: { fetchImpl?: FetchLike; listId?: string },
): Promise<GraphCallResult> {
  const listId = opts?.listId || "tasks";
  return callGraph(
    token,
    `me/todo/lists/${encodeURIComponent(listId)}/tasks`,
    "GET",
    undefined,
    { fetchImpl: opts?.fetchImpl },
  );
}

/** Calendar → /me/events */
export async function graphCreateEvent(
  token: string | undefined,
  event: { subject: string; start?: string; end?: string; body?: string },
  opts?: { fetchImpl?: FetchLike },
): Promise<GraphCallResult> {
  const start = event.start || new Date().toISOString();
  const end =
    event.end ||
    new Date(Date.parse(start) + 60 * 60 * 1000).toISOString();
  return callGraph(
    token,
    "me/events",
    "POST",
    {
      subject: event.subject,
      body: { contentType: "Text", content: event.body || "" },
      start: { dateTime: start, timeZone: "UTC" },
      end: { dateTime: end, timeZone: "UTC" },
    },
    { fetchImpl: opts?.fetchImpl },
  );
}

/** Mail → /me/sendMail */
export async function graphSendMail(
  token: string | undefined,
  mail: { to: string; subject: string; body: string },
  opts?: { fetchImpl?: FetchLike },
): Promise<GraphCallResult> {
  return callGraph(
    token,
    "me/sendMail",
    "POST",
    {
      message: {
        subject: mail.subject,
        body: { contentType: "Text", content: mail.body },
        toRecipients: [{ emailAddress: { address: mail.to } }],
      },
      saveToSentItems: true,
    },
    { fetchImpl: opts?.fetchImpl },
  );
}

/**
 * Spreadsheets → workbook path stub.
 * Full Excel workbook API is heavy; use drive item workbook session when wired.
 * Path: me/drive/root:/AAIS/exports/{name}:/workbook
 */
export async function graphWorkbookStub(
  token: string | undefined,
  name: string,
  opts?: { fetchImpl?: FetchLike },
): Promise<GraphCallResult> {
  const safe = name.replace(/[^\w.-]+/g, "_").slice(0, 80) || "export";
  return callGraph(
    token,
    `me/drive/root:/AAIS/exports/${safe}:/workbook`,
    "GET",
    undefined,
    { fetchImpl: opts?.fetchImpl },
  );
}
