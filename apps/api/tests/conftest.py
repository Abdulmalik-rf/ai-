"""Test fixtures.

Two layers:
  - Pure-unit tests (no fixtures needed): import + call functions directly.
  - Integration tests (`@pytest.mark.integration`): use the `client` fixture
    which spins up a TestClient against the real app, expecting the dev DB
    + Redis to be reachable.

Tests are deliberately light — we use the same code paths the live API
uses, instead of duplicating a separate test DB engine.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

# Override LLM provider before app import so signup tests don't try to mint
# Codex calls. The agent loop tests opt back in by setting LLM_PROVIDER=
# chatgpt-oauth in their own setup.
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_CHATGPT_TOKEN", "")


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fresh_email() -> str:
    """Random email per test so signup tests don't collide on the unique
    constraint. Use this any time a test creates a User."""
    return f"test-{uuid.uuid4().hex[:12]}@example.test"


@pytest.fixture()
def fresh_firm_name() -> str:
    return f"Test Firm {uuid.uuid4().hex[:8]}"
