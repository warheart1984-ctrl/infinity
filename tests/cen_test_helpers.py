"""Test helper: mint valid VT authority tokens for law-state adoptions.

Tokens are bound to the deterministic CEN transition id of the exact
law-state record, mirroring what an operator console would do.
"""

from __future__ import annotations

from src.cen_governance_bridge import (
    issue_authority_token,
    mint_vt_token_from_denial,
    law_record_digest,
    law_state_transition_id,
)


def mint_vt_token(sink: str, record: dict, *, token_id: str = "vt-test") -> dict:
    return issue_authority_token(
        token_id=token_id,
        token_type="VT",
        scope=["law:mutate"],
        transition_id=law_state_transition_id(sink, record),
        expires_at="2999-01-01T00:00:00.000Z",
    )


__all__ = ["law_record_digest", "law_state_transition_id", "mint_vt_token", "mint_vt_token_from_denial", "enable_cen_autochallenge", "cen_approved"]


def enable_cen_autochallenge(runtime) -> None:
    """Wrap adopt_* methods: on CEN VT refusal, mint a token bound to the
    refused transition (the challenge the server reveals) and retry once.
    Mirrors the real operator-console challenge-response flow."""
    from src.cen_governance_bridge import mint_vt_token_from_denial

    for name in list(dir(runtime)):
        if not name.startswith("adopt_"):
            continue
        original = getattr(runtime, name)
        if getattr(original, "_cen_autochallenged", False):
            continue

        def wrapped(*args, _orig=original, **kwargs):
            result = _orig(*args, **kwargs)
            if (
                isinstance(result, dict)
                and result.get("outcome") == "blocked"
                and isinstance(result.get("cen"), dict)
                and result["cen"].get("transition_id")
                and not kwargs.get("authority_token")
            ):
                kwargs["authority_token"] = mint_vt_token_from_denial(result["cen"])
                result = _orig(*args, **kwargs)
            return result

        wrapped._cen_autochallenged = True
        try:
            setattr(runtime, name, wrapped)
        except AttributeError:
            pass


def cen_approved(sink: str, record: dict, *, actor: str = "operator") -> dict:
    """Fixture helper: a law-state record carrying a valid CEN approval.
    Fixtures obey the same law as production writers — no unapproved sinks."""
    from src.cen_governance_bridge import cen_governance_bridge

    token = mint_vt_token(sink, record, token_id=f"vt-{law_state_transition_id(sink, record)[-12:]}")
    approval = cen_governance_bridge.gate_law_state_write(
        sink=sink, record=record, actor=actor, authority_token=token
    )
    assert approval.get("outcome") == "approved", approval
    return {**record, "cen_approval": approval}
