"""End-to-end proof that the live watch loop adapts dynamically.

Drives the real run_watch_live loop through a scripted background-brightness
sequence (the sample_provider seam) with a recording apply function (the
apply_preset seam), and asserts the loop actually switched and applied the
matching presets as the simulated background changed — not just that the
classifier in isolation can switch.
"""

from __future__ import annotations

from pathlib import Path

from term_chameleon.live_iterm import LiveApplyResult
from term_chameleon.watch import Sample
from term_chameleon.watch_live import (
    DEMO_CYCLE_LUMINANCES,
    WatchLiveConfig,
    demo_cycle_sample_provider,
    run_watch_live,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _run(luminances, *, stable=1, cooldown=0.0):
    """Run the live loop over a scripted brightness sequence; return applied modes."""
    samples = [Sample(lum) for lum in luminances]
    applied: list[str] = []

    def provider(index, _output_dir, _region):
        return samples[index - 1], f"sample-{index}"

    def apply(mode: str) -> LiveApplyResult:
        applied.append(mode)
        return LiveApplyResult(mode, True, ("set_transparency",), f"applied {mode}")

    clock = _FakeClock()
    events = run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=len(samples) - 1,
            stable=stable,
            cooldown=cooldown,
            output_dir=Path("/tmp"),  # unused: provider is injected
            dry_run=False,
            initial_mode="balanced",
        ),
        sample_provider=provider,
        apply_preset=apply,
        sleep=clock.sleep,
        clock=clock,
    )
    return applied, events


def test_live_loop_switches_as_background_changes():
    """Dark -> bright -> dark drives dark-glass -> bright-safe -> dark-glass, applied live."""
    applied, events = _run([0.05, 0.92, 0.05])

    assert applied == ["dark-glass", "bright-safe", "dark-glass"]
    # Every applied switch is reflected as an applied event in the loop output.
    applied_events = [e for e in events if e.applied]
    assert [e.mode for e in applied_events] == ["dark-glass", "bright-safe", "dark-glass"]


def test_live_loop_holds_when_background_is_stable():
    """A steady background switches once then holds — no thrash on each sample."""
    applied, _ = _run([0.05, 0.04, 0.06, 0.05])

    assert applied == ["dark-glass"]  # one switch from the 'balanced' initial mode, then holds


def test_live_loop_handles_high_variance_background():
    """A high-variance (mixed bright/dark) background routes to the high-variance-safe mode."""
    high_var = [Sample(0.5, 0.20)]

    def provider(index, _output_dir, _region):
        return high_var[index - 1], f"sample-{index}"

    recorded: list[str] = []
    clock = _FakeClock()
    run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=0.5,
            stable=1,
            cooldown=0,
            output_dir=Path("/tmp"),
            dry_run=False,
            initial_mode="balanced",
        ),
        sample_provider=provider,
        apply_preset=lambda m: (recorded.append(m), LiveApplyResult(m, True, (), m))[1],
        sleep=clock.sleep,
        clock=clock,
    )
    assert recorded == ["high-variance-safe"]


def test_demo_cycle_provider_alternates_bright_and_dark():
    """The demo-cycle provider returns a repeating bright/dark pattern by index."""
    from pathlib import Path

    seen = [demo_cycle_sample_provider(i, Path("/tmp"), None)[0].luminance for i in range(1, 9)]
    # Two cycles of DEMO_CYCLE_LUMINANCES.
    assert seen == list(DEMO_CYCLE_LUMINANCES) * 2
    # It spans both a dark (<0.35) and a bright (>0.65) value so it forces switches.
    assert min(seen) < 0.35
    assert max(seen) > 0.65


def test_demo_cycle_drives_real_loop_to_switch():
    """watch-live's demo-cycle provider makes the real loop switch modes on a timer."""
    from pathlib import Path

    applied: list[str] = []
    clock = _FakeClock()
    run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=4,
            stable=1,
            cooldown=0,
            output_dir=Path("/tmp"),
            dry_run=False,
            initial_mode="balanced",
        ),
        sample_provider=demo_cycle_sample_provider,
        apply_preset=lambda m: (applied.append(m), LiveApplyResult(m, True, (), m))[1],
        sleep=clock.sleep,
        clock=clock,
    )
    # Over a dark,dark,bright,bright,dark cycle it applies dark-glass then bright-safe
    # then dark-glass again — visibly auto-adapting with no input.
    assert "dark-glass" in applied
    assert "bright-safe" in applied
    assert applied.index("dark-glass") < applied.index("bright-safe")
