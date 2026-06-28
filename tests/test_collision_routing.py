"""Phase 2: a splotchy / colliding background (high variance) must route to a rung
that genuinely escalates the collision-clearing levers — more blur to homogenize,
no more transparency, and at least as much minimum-contrast insurance — versus the
benign-brightness rungs. This is how the worst-case design handles the local
per-color collision class (e.g. green text over a green wallpaper patch) without
any per-cell code."""

from __future__ import annotations

from term_chameleon.presets import PRESETS
from term_chameleon.watch import Sample, classify_sample

HIGH_VARIANCE = 0.20  # a clearly splotchy backdrop (variance >= 0.08 threshold)


def _mode_for(luminance: float, variance: float) -> str:
    return classify_sample(Sample(luminance, variance)).mode


def test_high_variance_routes_to_high_variance_safe():
    # Regardless of average brightness, a splotchy backdrop is treated as a
    # collision risk and routed to the high-variance rung.
    for lum in (0.10, 0.50, 0.90):
        assert _mode_for(lum, HIGH_VARIANCE) == "high-variance-safe"


def test_high_variance_rung_escalates_versus_benign_brightness():
    """The high-variance rung must homogenize harder (more blur) and be no more
    transparent than the uniform dark/mid rungs it is chosen instead of."""
    hv = PRESETS["high-variance-safe"]
    for benign in ("dark-glass", "balanced"):
        b = PRESETS[benign]
        assert hv.blur_radius >= b.blur_radius, f"need >= blur than {benign} to homogenize"
        assert hv.transparency <= b.transparency, f"need <= transparency than {benign}"
        assert hv.minimum_contrast >= b.minimum_contrast, f"need >= min-contrast than {benign}"
    assert hv.blur is True  # blur must be on for the homogenizer to work


def test_variance_threshold_dominates_brightness():
    """A bright-but-uniform backdrop is bright-safe, but the SAME brightness with
    high variance escalates to high-variance-safe — variance takes precedence."""
    assert _mode_for(0.90, 0.0) == "bright-safe"
    assert _mode_for(0.90, HIGH_VARIANCE) == "high-variance-safe"


def test_uniform_backgrounds_do_not_overreact():
    # A calm uniform backdrop must NOT be pushed to the aggressive rung.
    assert _mode_for(0.10, 0.0) == "dark-glass"
    assert _mode_for(0.50, 0.02) == "balanced"
