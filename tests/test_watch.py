from term_chameleon.cli import main
from term_chameleon.watch import HIGH_RISK, ModeSelector, Sample, classify_sample, simulate_modes


def test_classifies_dark_bright_balanced_and_variance():
    assert classify_sample(Sample(0.2)).risk == "dark-low-risk"
    assert classify_sample(Sample(0.5)).risk == "balanced-medium-risk"
    assert classify_sample(Sample(0.8)).risk == "bright-high-risk"
    assert classify_sample(Sample(0.5, 0.12)).risk == "high-variance-high-risk"


def test_mode_selector_requires_stable_samples():
    selector = ModeSelector(stable_samples_required=3)
    assert selector.observe(Sample(0.8))[0] == "balanced"
    assert selector.observe(Sample(0.82))[0] == "balanced"
    mode, _classification, switched = selector.observe(Sample(0.81))
    assert mode == "bright-safe"
    assert switched is True


def test_mode_selector_resets_candidate_on_current_mode():
    selector = ModeSelector(stable_samples_required=2)
    selector.observe(Sample(0.8))
    mode, _classification, switched = selector.observe(Sample(0.5))
    assert mode == "balanced"
    assert switched is False
    selector.observe(Sample(0.8))
    mode, _classification, switched = selector.observe(Sample(0.8))
    assert mode == "bright-safe"
    assert switched is True


def test_simulate_modes_records_events():
    events = simulate_modes([Sample(0.8), Sample(0.8), Sample(0.8)])
    assert events[-1] == ("bright-high-risk", "bright-safe", True)


def test_watch_sim_cli(capsys):
    assert main(["watch-sim", "0.8", "0.8", "0.8", "0.5:0.12"]) == 0
    out = capsys.readouterr().out
    assert "mode=bright-safe switch" in out
    assert "risk=high-variance-high-risk" in out


def test_high_risk_set_is_defined_in_watch_module():
    """HIGH_RISK is the canonical set shared by both anti-thrash gates."""
    assert "bright-high-risk" in HIGH_RISK
    assert "high-variance-high-risk" in HIGH_RISK


def test_min_luminance_delta_gate_bypassed_for_bright_high_risk():
    """A bright-high-risk sample must switch even when the luminance delta is
    below min_luminance_delta (0.10).  Scenario: switch into 'balanced' at
    luminance=0.58 sets _last_switch_luminance; next sample at 0.66 classifies
    as bright-high-risk (delta=0.08 < 0.10) but must still switch to bright-safe.
    """
    selector = ModeSelector(stable_samples_required=1, min_luminance_delta=0.10)
    # First switch: balanced → dark-glass at luminance=0.20 to set the baseline.
    # We need current_mode != candidate to trigger a switch; start from 'bright-safe'
    # so that a balanced sample at 0.58 causes a real switch and records the lum.
    selector.current_mode = "bright-safe"
    selector._last_switch_luminance = None  # type: ignore[attr-defined]

    # Switch into 'balanced' at 0.58 — sets _last_switch_luminance = 0.58.
    _, _, switched = selector.observe(Sample(0.58))
    assert switched is True
    assert selector.current_mode == "balanced"
    assert selector._last_switch_luminance == 0.58  # type: ignore[attr-defined]

    # 0.66 → bright-high-risk, delta = 0.08 < 0.10; must switch despite small delta.
    _, classification, switched = selector.observe(Sample(0.66))
    assert classification.risk == "bright-high-risk"
    assert switched is True, (
        "bright-high-risk must bypass the min_luminance_delta gate "
        f"(delta={abs(0.66 - 0.58):.2f} < {selector.min_luminance_delta})"
    )
    assert selector.current_mode == "bright-safe"


def test_min_luminance_delta_gate_still_blocks_low_risk_small_delta():
    """The delta gate must still suppress oscillation for non-emergency modes.

    Scenario: switch into balanced at lum=0.36 (sets _last_switch_luminance=0.36),
    then feed a dark sample at 0.30 (dark-low-risk, delta=0.06 < 0.10).
    The gate must hold the mode because this is a low-risk candidate.
    """
    # Switch into balanced from bright-safe at luminance 0.36.
    # 0.36 is in the balanced range [0.35, 0.65] and the delta from bright-safe
    # (no prior switch) is irrelevant — _last_switch_luminance starts as None.
    selector = ModeSelector(stable_samples_required=1, min_luminance_delta=0.10)
    selector.current_mode = "bright-safe"
    _, _, sw = selector.observe(Sample(0.36))
    assert sw and selector.current_mode == "balanced"
    assert selector._last_switch_luminance == 0.36  # type: ignore[attr-defined]

    # 0.30 → dark-low-risk; delta = |0.30 - 0.36| = 0.06 < 0.10.
    # Because dark-low-risk is not in HIGH_RISK the gate must block this switch.
    _, classification, switched = selector.observe(Sample(0.30))
    assert classification.risk == "dark-low-risk"
    assert switched is False, "low-risk small-delta switch must still be suppressed"
