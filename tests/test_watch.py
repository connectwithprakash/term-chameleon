from term_chameleon.cli import main
from term_chameleon.watch import ModeSelector, Sample, classify_sample, simulate_modes


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
