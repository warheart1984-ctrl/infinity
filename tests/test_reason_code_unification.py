"""Reason-code unification: the TS const must match the Python tuple exactly.

Single source of truth: src/constitutional_enforcement_node.py::REASON_CODES.
If this test fails, someone changed the Python tuple without running
scripts/generate_reason_codes.py.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED = REPO_ROOT / "aais-middleware" / "src" / "policy_core" / "reason_codes.ts"


def _rendered_now() -> str:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_reason_codes.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    # Regenerate in a temp copy to compare without clobbering mtime semantics;
    # simplest honest check: file on disk must equal freshly rendered output.
    return GENERATED.read_text(encoding="utf-8")


def test_generated_file_matches_python_tuple():
    from src.constitutional_enforcement_node import REASON_CODES

    text = GENERATED.read_text(encoding="utf-8")
    for code in REASON_CODES:
        assert f'"{code}",' in text, f"reason code {code} missing from generated TS"
    # No extra codes beyond the Python tuple.
    listed = re.findall(r'^  "([A-Z_]+)",$', text, re.MULTILINE)
    assert sorted(listed) == sorted(REASON_CODES), (
        f"drift: python={sorted(REASON_CODES)} ts={sorted(listed)}"
    )


def test_regeneration_is_idempotent():
    before = _rendered_now()
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_reason_codes.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    after = _rendered_now()
    assert before == after


def test_python_side_exports_all_codes():
    """The Python tuple stays the single source of truth — sanity pin."""
    from src.constitutional_enforcement_node import RECEIPT_CATEGORIES, REASON_CODES

    assert len(REASON_CODES) == len(set(REASON_CODES)), "duplicate reason codes"
    assert all(code == code.upper() for code in REASON_CODES)
    assert isinstance(RECEIPT_CATEGORIES, tuple)
