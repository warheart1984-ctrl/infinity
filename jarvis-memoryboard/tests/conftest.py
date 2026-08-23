"""Shared test isolation — EMR dynamics sidecar must never touch repo data/."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import app.emr as emr
import app.amul as amul


@pytest.fixture(autouse=True)
def _isolated_dynamics_sidecar(tmp_path):
    """Point EMR + AMUL storage at per-test temp files.

    Unit tests must not read or write real data/ files; durability behavior
    is covered explicitly in test_emr_dynamics.py / test_amul.py.
    """
    sidecar = Path(tempfile.mktemp(suffix="-dynamics.json", dir=str(tmp_path)))
    original = emr.DYNAMICS_PATH
    emr.DYNAMICS_PATH = str(sidecar)
    emr._dynamics_loaded = False  # force reload against isolated path

    amul_path = Path(tempfile.mktemp(suffix="-field.jsonl", dir=str(tmp_path)))
    original_field_path = amul.FIELD_PATH
    amul.FIELD_PATH = str(amul_path)
    amul.reset_field_for_tests()

    yield
    emr.DYNAMICS_PATH = original
    emr._dynamics_loaded = False
    amul.FIELD_PATH = original_field_path
    amul.reset_field_for_tests()
    emr.reset_stm_for_tests()
