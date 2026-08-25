/**
 * Mythic: Gmail conduit
 * Engineering: gmailSend / sendGmailEmail
 */
import type { FetchLike } from "./graph_client.js";

export const GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1";

export interface GmailSendResult {
  ok: boolean;
  status: number;
  data?: unknown;
  error?: string;
  reasonCode: string;
  simulated?: boolean;
}

function buildRawMessage(to: string, subject: string, body: string): string {
  const lines = [
    `To: ${to}`,
    `Subject: ${subject}`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "",
    body,
  ];
  const raw = lines.join("\r\n");
  return Buffer.from(raw, "utf8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** Alias: sendGmailEmail */
export async function sendGmailEmail(
  token: string | undefined,
  mail: { to: string; subject: string; body: string },
  opts?: { fetchImpl?: FetchLike; forceSimulate?: boolean },
): Promise<GmailSendResult> {
  return gmailSend(token, mail, opts);
}

export async function gmailSend(
  token: string | undefined,
  mail: { to: string; subject: string; body: string },
  opts?: { fetchImpl?: FetchLike; forceSimulate?: boolean },
): Promise<GmailSendResult> {
  if (!token || opts?.forceSimulate) {
    return {
      ok: true,
      status: 200,
      simulated: true,
      reasonCode: "GMAIL_SIMULATE",
      data: {
        simulated: true,
        to: mail.to,
        subject: mail.subject,
        body: mail.body.slice(0, 2000),
      },
    };
  }

  const fetchImpl = opts?.fetchImpl ?? (globalThis.fetch as FetchLike);
  if (!fetchImpl) {
    return {
      ok: false,
      status: 0,
      reasonCode: "GMAIL_NO_FETCH",
      error: "fetch unavailable",
    };
  }

  try {
    const raw = buildRawMessage(mail.to, mail.subject, mail.body);
    const res = await fetchImpl(`${GMAIL_API_BASE}/users/me/messages/send`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ raw }),
    });
    const text = await res.text();
    let data: unknown;
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
        error: `Gmail HTTP ${res.status}`,
        reasonCode: "GMAIL_HTTP_ERROR",
      };
    }
    return {
      ok: true,
      status: res.status,
      data,
      reasonCode: "GMAIL_LIVE_OK",
    };
  } catch (err) {
    return {
      ok: false,
      status: 0,
      error: err instanceof Error ? err.message : String(err),
      reasonCode: "GMAIL_NETWORK_ERROR",
    };
  }
}
