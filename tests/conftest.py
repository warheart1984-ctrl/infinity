"""Shared pytest fixtures for AAIS test isolation."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

import pytest


# Test modules import ``src.api`` during collection, before fixtures run.  Give
# every pytest process its own durable-session path at import time so a local
# ``AAIS_PERSIST_SESSIONS=1`` setting can never load, expire, or rewrite the
# operator's live conversation snapshot.
_SESSION_SNAPSHOT_SANDBOX = tempfile.TemporaryDirectory(
    prefix="aais-pytest-conversation-sessions-"
)
os.environ["AAIS_SESSION_SNAPSHOT_PATH"] = str(
    Path(_SESSION_SNAPSHOT_SANDBOX.name) / "conversation_sessions.json"
)


@pytest.fixture(scope="session", autouse=True)
def _genome_boot_warn_for_fastapi():
    """FastAPI lifespan uses strict genome boot by default; warn for test sessions."""
    prior = os.environ.get("AAIS_GENOME_BOOT")
    os.environ["AAIS_GENOME_BOOT"] = "warn"
    yield
    if prior is None:
        os.environ.pop("AAIS_GENOME_BOOT", None)
    else:
        os.environ["AAIS_GENOME_BOOT"] = prior


@pytest.fixture(autouse=True)
def _reset_otem_execution_substrate_singleton():
    from src.otem_execution_substrate import reset_otem_execution_substrate

    reset_otem_execution_substrate()
    yield
    reset_otem_execution_substrate()
