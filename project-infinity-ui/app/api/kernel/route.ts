// app/api/kernel/route.ts
//
// Kernel proxy — bridges the Dialogue Surface to Project Infinity's
// constitutional boundary. The sanctioned crossing is POST /sovereign/gate
// (CEN admission): approvals carry full commitCertificates, denials are
// evidence, and VT-gated actions return a re-mintable challenge shape that
// surfaces here as AWAIT HUMAN APPROVAL.
//
// Contract preserved from the UI design:
//   request  : { proposal: string, actor?: string, bounds?: object }
//   response : { verdict: "ALLOW" | "DENY" | "AWAIT", receipt: {...} }
//
// Override the target with SOVEREIGN_GATE_URL (default: local AAIS stack).

import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "node:crypto";

const KERNEL_URL =
  process.env.SOVEREIGN_GATE_URL ?? "http://127.0.0.1:8000/sovereign/gate";

interface SovereignGateResponse {
  outcome?: string;
  reason?: string;
  reason_code?: string;
  reason_detail?: string;
  transition_id?: string;
  cen_receipt_id?: string;
  cen_receipt_hash?: string;
  evidence_receipt_id?: string;
  committed?: boolean;
  commitCertificate?: Record<string, unknown>;
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    const gateResponse = await fetch(KERNEL_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transition_id: `transition:ui-${randomUUID().slice(0, 8)}`,
        transition_type: "runtime_action",
        payload: { proposal: String(body.proposal ?? "") },
        requested_capabilities: ["state:commit"],
        granted_capabilities: ["state:commit", "workflow:execute"],
        actor: body.actor ?? "user",
      }),
    });

    const data: SovereignGateResponse = await gateResponse.json();

    // Fail-closed is never masked as evidence.
    if (!gateResponse.ok || data.reason === "cen_failed_closed") {
      return NextResponse.json(
        {
          error: "Kernel unreachable",
          detail: data.reason_detail ?? `gate HTTP ${gateResponse.status}`,
          status: gateResponse.status,
        },
        { status: 502 },
      );
    }

    if (data.outcome === "approved") {
      return NextResponse.json({
        verdict: "ALLOW",
        receipt: {
          receipt_id: data.cen_receipt_id,
          hash: data.cen_receipt_hash,
          bounded: true,
          evidence_receipt_id: data.evidence_receipt_id,
          certificate: data.commitCertificate,
        },
      });
    }

    // Denials are evidence. VT challenges surface as AWAIT HUMAN APPROVAL —
    // the operator mints a token against transition_id and resubmits fresh.
    if (data.reason === "cen_vt_required") {
      return NextResponse.json({
        verdict: "AWAIT",
        receipt: {
          receipt_id: data.cen_receipt_id,
          transition_id: data.transition_id,
          reason_code: data.reason_code,
          reason_detail: data.reason_detail,
          challenge: "mint_vt_token_from_denial",
          committed: false,
        },
      });
    }

    return NextResponse.json({
      verdict: "DENY",
      receipt: {
        receipt_id: data.cen_receipt_id,
        reason_code: data.reason_code,
        reason_detail: data.reason_detail,
        committed: false,
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Kernel unreachable", detail: String(e) },
      { status: 500 },
    );
  }
}
