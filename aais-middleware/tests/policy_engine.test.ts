import assert from "node:assert/strict";
import test from "node:test";
import { evaluatePolicy, matchClause, policyEvalView } from "../src/policy_core/policy_engine.js";
import { normalizeRequest } from "../src/intent_bus/intent_normalizer.js";

test("matchClause path eq/in/contains", () => {
  const view = {
    intent: { type: "mixed", tags: ["code", "write"] },
    policy: { riskLevel: "high" },
  };
  assert.equal(matchClause({ path: "policy.riskLevel", eq: "high" }, view), true);
  assert.equal(matchClause({ path: "intent.type", in: ["task", "mixed"] }, view), true);
  assert.equal(matchClause({ path: "intent.tags", contains: "code" }, view), true);
  assert.equal(
    matchClause(
      {
        all: [
          { path: "policy.riskLevel", eq: "high" },
          { path: "intent.tags", contains: "code" },
        ],
      },
      view,
    ),
    true,
  );
});

test("evaluatePolicy denies high_risk_code on gpt_tools", () => {
  const req = normalizeRequest({
    intent: { raw: "code a workflow skill", type: "skill", tags: ["code", "skill"] },
    context: { user: "op" },
    policy: { riskLevel: "high" },
    skills: [{ id: "s1", action: "code", target: "scaffold" }],
  });
  const decision = evaluatePolicy(req);
  assert.ok(decision.matchedRuleIds.includes("high_risk_code"));
  assert.ok(decision.blockedProviders.includes("gpt_tools"));
  assert.ok(!decision.approvedProviders.includes("gpt_tools"));
});

test("evaluatePolicy allows ms_tasks on normal mixed plan", () => {
  const req = normalizeRequest({
    intent: "Plan my week and write the email",
    context: { user: "op" },
    policy: { riskLevel: "normal" },
  });
  const view = policyEvalView(req);
  const policyView = view.policy as { riskLevel: string };
  assert.equal(policyView.riskLevel, "normal");
  const decision = evaluatePolicy(req);
  assert.ok(decision.matchedRuleIds.includes("allow_ms_tasks_normal"));
  assert.ok(decision.approvedProviders.includes("ms_tasks"));
});
