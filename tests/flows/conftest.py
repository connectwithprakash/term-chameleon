"""Pytest wiring for the user-flow suite.

- Registers the `visual` and `flow` markers.
- Adds `--run-visual` to opt into the real-iTerm2 Cua Driver layer.
- Exposes detected environment capabilities as a fixture.
"""

from __future__ import annotations

import pytest
from runner import detect_capabilities


def pytest_addoption(parser):
    parser.addoption(
        "--run-visual",
        action="store_true",
        default=False,
        help="Run visual flows that drive real iTerm2 via the Cua Driver (macOS only).",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "flow: a term-chameleon user-flow test")
    config.addinivalue_line("markers", "visual: drives real iTerm2 via Cua Driver (slow, macOS)")


@pytest.fixture(scope="session")
def capabilities() -> set[str]:
    return detect_capabilities()
