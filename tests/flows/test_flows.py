"""Parametrize every flow spec in specs/ into a pytest case.

Deterministic flows run by default. Visual flows require --run-visual and the
environment capabilities they declare; otherwise they are skipped (never failed),
so the suite stays green on Linux/CI.
"""

from __future__ import annotations

import tempfile

import pytest
from runner import Flow, detect_capabilities, discover_flows, run_deterministic_step

try:
    from visual import run_visual_step  # optional; only needed for visual flows
except Exception:  # pragma: no cover - import guard
    run_visual_step = None

_FLOWS = discover_flows()


def _flow_id(flow: Flow) -> str:
    return flow.name


@pytest.mark.flow
@pytest.mark.parametrize("flow", _FLOWS, ids=[_flow_id(f) for f in _FLOWS])
def test_flow(flow: Flow, request):
    is_visual = flow.layer == "visual"

    if is_visual:
        if not request.config.getoption("--run-visual"):
            pytest.skip("visual flow; pass --run-visual to run")
        missing = set(flow.requires) - detect_capabilities()
        if missing:
            pytest.skip(f"missing capabilities for visual flow: {sorted(missing)}")
        if run_visual_step is None:
            pytest.skip("visual runner unavailable")

    with tempfile.TemporaryDirectory(prefix=f"tc-flow-{flow.name}-") as tmp:
        variables = dict(flow.vars)
        variables["workdir"] = tmp

        for index, step in enumerate(flow.steps):
            label = step.name or step.run or f"step-{index}"

            if step.visual:
                if not is_visual:
                    pytest.fail(f"{flow.name}: visual step in a non-visual flow ({label})")
                result = run_visual_step(step, variables)
            else:
                result = run_deterministic_step(step, variables)

            assert result.ok, (
                f"flow {flow.name!r} step {label!r} failed:\n  "
                + "\n  ".join(result.failures)
                + (f"\n--- stdout ---\n{result.stdout}" if result.stdout else "")
                + (f"\n--- stderr ---\n{result.stderr}" if result.stderr else "")
            )


def test_specs_are_well_formed():
    """Every spec parses and declares the required fields."""
    assert _FLOWS, "no flow specs discovered"
    for flow in _FLOWS:
        assert flow.name, f"{flow.path} missing name"
        assert flow.steps, f"{flow.name} has no steps"
        assert flow.layer in {"deterministic", "visual"}, f"{flow.name} bad layer {flow.layer}"
        assert flow.description, f"{flow.name} missing description (flows are documentation)"
