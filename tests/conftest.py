"""Pytest configuration: mark tests by directory so suites can be selected.

    pytest -m unit          # pure functions, no model downloads, milliseconds
    pytest -m integration   # runner / API / dataset plumbing (loads the small embedding model)
    pytest -m evaluation    # full retrieval on the golden sets; includes the CI gate
"""
from pathlib import Path

import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        parts = Path(str(item.fspath)).parts
        for suite in ("unit", "integration", "evaluation"):
            if suite in parts:
                item.add_marker(getattr(pytest.mark, suite))
