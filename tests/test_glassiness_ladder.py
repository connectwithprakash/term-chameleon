"""Phase 1: the calibrated glassiness ladder and the 'only default bg uses
transparency' lever, across all three apply paths (profile dict, live setters,
generated live-adapter)."""

from __future__ import annotations

from term_chameleon.iterm_api import live_adapter_script, setter_mappings
from term_chameleon.presets import (
    GLASSINESS_LADDER,
    PRESETS,
    apply_preset_to_profile_dict,
    get_preset,
)

ONLY_DEFAULT_BG_KEY = "Only The Default BG Color Uses Transparency"
ONLY_DEFAULT_BG_SETTER = "set_only_the_default_bg_color_uses_transparency"


def test_ladder_covers_every_preset_once():
    assert set(GLASSINESS_LADDER) == set(PRESETS)
    assert len(GLASSINESS_LADDER) == len(set(GLASSINESS_LADDER))


def test_ladder_invariant_transparency_down_min_contrast_up():
    """As the ladder steps toward opacity, transparency must be non-increasing and
    minimum contrast non-decreasing — the calibration the watcher steps along."""
    rungs = [PRESETS[name] for name in GLASSINESS_LADDER]
    for lower, higher in zip(rungs, rungs[1:], strict=False):
        assert higher.transparency <= lower.transparency, (
            f"transparency rose from {lower.name} to {higher.name}"
        )
        assert higher.minimum_contrast >= lower.minimum_contrast, (
            f"minimum contrast fell from {lower.name} to {higher.name}"
        )


def test_every_preset_keeps_only_default_bg_transparent_by_default():
    for preset in PRESETS.values():
        assert preset.only_default_bg_transparent is True


def test_only_default_bg_key_written_to_profile_dict():
    profile: dict = {}
    apply_preset_to_profile_dict(profile, get_preset("dark-glass"))
    assert profile[ONLY_DEFAULT_BG_KEY] is True


def test_only_default_bg_setter_in_setter_mappings():
    mapping = dict(setter_mappings(get_preset("bright-safe")))
    assert mapping[ONLY_DEFAULT_BG_SETTER] is True


def test_only_default_bg_setter_in_generated_live_adapter():
    script = live_adapter_script(preset_name="balanced")
    assert ONLY_DEFAULT_BG_SETTER in script


def test_min_contrast_applied_on_every_rung():
    """Min-contrast is always-on insurance — every rung sets a positive floor."""
    for preset in PRESETS.values():
        mapping = dict(setter_mappings(preset))
        assert mapping["set_minimum_contrast"] == preset.minimum_contrast
        assert preset.minimum_contrast > 0
