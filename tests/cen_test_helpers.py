"""Test helper: mint valid VT authority tokens for law-state adoptions.

Tokens are bound to the deterministic CEN transition id of the exact
law-state record, mirroring what an operator console would do.
"""

from __future__ import annotations

from src.cen_governance_bridge import (
    issue_authority_token,
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


__all__ = ["law_record_digest", "law_state_transition_id", "mint_vt_token"]
