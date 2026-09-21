"""Pytest configuration: mark tests by directory so suites can be selected.

    pytest -m unit          # pure functions, no model downloads, milliseconds
    pytest -m integration   # runner / API / dataset plumbing (loads the small embedding model)
    pytest -m evaluation    # full retrieval on the golden sets; includes the CI gate
"""
import os
from pathlib import Path

import pytest

# Tests must never call an LLM, whatever a developer's local .env says. This runs before
# `src` is imported (which loads .env without overriding values already set here).
os.environ["GENERATION_BACKEND"] = "extractive"
os.environ["USE_LLM_JUDGE"] = "false"
os.environ["GROQ_API_KEY"] = ""  # empty (not unset) so .env cannot repopulate it


def pytest_collection_modifyitems(items):
    for item in items:
        parts = Path(str(item.fspath)).parts
        for suite in ("unit", "integration", "evaluation"):
            if suite in parts:
                item.add_marker(getattr(pytest.mark, suite))
