// app/page.tsx
"use client";

import React, { useState } from "react";

type KernelReply = {
  verdict: "ALLOW" | "DENY" | "AWAIT";
  receipt: {
    receipt_id?: string;
    hash?: string;
    bounded?: boolean;
    transition_id?: string;
    reason_code?: string;
    reason_detail?: string;
    challenge?: string;
    evidence_receipt_id?: string;
    certificate?: Record<string, unknown>;
    committed?: boolean;
  };
};

type Message =
  | { role: "user"; content: string }
  | { role: "kernel"; content: string; verdict?: KernelReply };

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSend() {
    if (!input.trim()) return;
    const proposal = input.trim();

    setMessages((prev) => [...prev, { role: "user", content: proposal }]);
    setInput("");
    setSending(true);

    try {
      const res = await fetch("/api/kernel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          proposal,
          actor: "user",
          bounds: { max_risk: 0.7 },
        }),
      });

      const data: KernelReply & { error?: string; detail?: string } =
        await res.json();

      if (data.error) {
        setMessages((prev) => [
          ...prev,
          { role: "kernel", content: `Kernel error: ${data.error} — ${data.detail ?? ""}` },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "kernel",
            content: `Verdict: ${data.verdict}`,
            verdict: data,
          },
        ]);
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "kernel", content: `Kernel error: ${String(e)}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-screen bg-gradient-to-b from-slate-900 via-slate-950 to-black text-slate-100">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-800 bg-slate-950/80 px-4 py-4 flex flex-col">
        <div className="font-semibold text-sm tracking-wide mb-4">
          ∞ Project Infinity
        </div>
        <nav className="space-y-2">
          <button className="w-full text-left text-xs px-3 py-2 rounded-md bg-slate-800/70 text-slate-100">
            Chat
          </button>
          <button className="w-full text-left text-xs px-3 py-2 rounded-md text-slate-400 hover:bg-slate-800/40">
            Agents
          </button>
          <button className="w-full text-left text-xs px-3 py-2 rounded-md text-slate-400 hover:bg-slate-800/40">
            Receipts
          </button>
          <button className="w-full text-left text-xs px-3 py-2 rounded-md text-slate-400 hover:bg-slate-800/40">
            Settings
          </button>
        </nav>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-950/70 backdrop-blur">
          <div className="text-sm font-medium">
            Infinity Constitutional Kernel
          </div>
          <div className="flex items-center gap-2 text-xs px-3 py-1 rounded-full border border-slate-600 text-slate-300">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" />
            {sending ? "Evaluating…" : "Bounded · Kernel Online"}
          </div>
        </header>

        {/* Chat area */}
        <main className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-xs text-slate-500 mt-10">
              Propose a bounded action. Every verdict is receipted by the
              constitutional kernel — approvals carry full commit
              certificates; denials are evidence.
            </div>
          )}
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-xl rounded-2xl border border-slate-700 bg-slate-900/90 px-4 py-3 shadow-lg">
                  <div className="text-[11px] text-slate-400 mb-1">You</div>
                  <div className="text-sm">{m.content}</div>
                </div>
              </div>
            ) : (
              <div key={i} className="flex justify-start">
                <div className="max-w-xl rounded-2xl border border-slate-700 bg-slate-950/90 px-4 py-3 shadow-lg">
                  <div className="text-[11px] text-slate-400 mb-1">
                    Infinity Kernel
                  </div>
                  <div className="text-sm">
                    {m.verdict ? (
                      <>
                        Verdict:
                        <VerdictPill verdict={m.verdict.verdict} />
                        {m.verdict.verdict === "AWAIT" &&
                          m.verdict.receipt.reason_detail && (
                            <p className="mt-2 text-[12px] text-slate-400">
                              {m.verdict.receipt.reason_detail}. Mint a VT
                              token against{" "}
                              <code className="text-amber-300">
                                {m.verdict.receipt.transition_id}
                              </code>{" "}
                              and resubmit as a fresh transition.
                            </p>
                          )}
                        {m.verdict.receipt.certificate && (
                          <details className="mt-2">
                            <summary className="cursor-pointer text-[11px] text-indigo-300">
                              commitCertificate
                            </summary>
                            <pre className="mt-2 text-[11px] font-mono bg-slate-900/90 border border-slate-800 rounded-md px-3 py-2 overflow-x-auto">
{JSON.stringify(m.verdict.receipt.certificate, null, 2)}
                            </pre>
                          </details>
                        )}
                        <pre className="mt-2 text-[11px] font-mono bg-slate-900/90 border border-slate-800 rounded-md px-3 py-2 overflow-x-auto">
{JSON.stringify(
  {
    receipt_id: m.verdict.receipt.receipt_id,
    hash: m.verdict.receipt.hash,
    reason_code: m.verdict.receipt.reason_code,
    committed: m.verdict.receipt.committed ?? true,
  },
  null,
  2,
)}
                        </pre>
                      </>
                    ) : (
                      m.content
                    )}
                  </div>
                </div>
              </div>
            )
          )}
        </main>

        {/* Input bar */}
        <footer className="px-6 py-3 border-t border-slate-800 bg-slate-950/80 backdrop-blur flex items-center gap-3">
          <input
            className="flex-1 rounded-full border border-slate-700 bg-slate-900/90 px-4 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            placeholder="Propose an action, ask a question, or paste JSON…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !sending) handleSend();
            }}
          />
          <button className="text-xs px-3 py-2 rounded-full border border-slate-600 bg-slate-900/80 text-slate-300 hover:bg-slate-800/80">
            Attach JSON
          </button>
          <button className="text-xs px-3 py-2 rounded-full border border-slate-600 bg-slate-900/80 text-slate-300 hover:bg-slate-800/80">
            View Receipts
          </button>
          <button className="text-xs px-4 py-2 rounded-full bg-indigo-500 hover:bg-indigo-400 text-white font-medium"
            disabled={sending}
            onClick={handleSend}
          >
            {sending ? "Sending…" : "Send"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function VerdictPill({ verdict }: { verdict: KernelReply["verdict"] }) {
  const base =
    "inline-flex items-center ml-2 px-2 py-0.5 rounded-full text-[11px] font-medium border";
  if (verdict === "ALLOW")
    return (
      <span
        className={`${base} border-emerald-500/70 bg-emerald-500/10 text-emerald-400`}
      >
        ALLOW
      </span>
    );
  if (verdict === "DENY")
    return (
      <span
        className={`${base} border-red-500/70 bg-red-500/10 text-red-400`}
      >
        DENY
      </span>
    );
  return (
    <span
      className={`${base} border-amber-400/70 bg-amber-400/10 text-amber-300`}
    >
      AWAIT HUMAN APPROVAL
    </span>
  );
}
