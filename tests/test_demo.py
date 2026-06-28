import pytest

from term_chameleon.commands import demo as demo_module
from term_chameleon.live_iterm import LiveApplyResult


def test_demo_applies_each_preset_in_order(monkeypatch):
    applied: list[str] = []

    def apply(preset: str) -> LiveApplyResult:
        applied.append(preset)
        return LiveApplyResult(preset, True, ("set_transparency",), f"applied {preset}")

    monkeypatch.setattr(demo_module, "apply_preset_to_current_session", apply)

    rc = demo_module.demo(presets=("dark-glass", "bright-safe"), hold=0, sleep=lambda _s: None)

    assert rc == 0
    assert applied == ["dark-glass", "bright-safe"]


def test_demo_holds_between_presets_but_not_after_last(monkeypatch):
    monkeypatch.setattr(
        demo_module,
        "apply_preset_to_current_session",
        lambda p: LiveApplyResult(p, True, (), "ok"),
    )
    sleeps: list[float] = []

    demo_module.demo(
        presets=("dark-glass", "balanced", "bright-safe"),
        hold=2.5,
        sleep=sleeps.append,
    )

    # One hold between each adjacent pair, none after the final preset.
    assert sleeps == [2.5, 2.5]


def test_demo_rejects_unknown_preset():
    with pytest.raises(ValueError, match="unknown preset"):
        demo_module.demo(presets=("not-a-real-preset",))


def test_demo_returns_1_when_no_live_session(monkeypatch):
    def raise_no_session(_preset):
        raise RuntimeError("no current iTerm2 session")

    monkeypatch.setattr(demo_module, "apply_preset_to_current_session", raise_no_session)

    rc = demo_module.demo(presets=("dark-glass",), hold=0, sleep=lambda _s: None)

    assert rc == 1
