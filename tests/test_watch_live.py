from pathlib import Path

import term_chameleon.watch_live as watch_live_module
from term_chameleon.images import Region
from term_chameleon.iterm_window import WindowBoundsResult
from term_chameleon.live_iterm import LiveApplyResult
from term_chameleon.watch import Sample
from term_chameleon.watch_live import WatchLiveConfig, run_watch_live


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_prune_artifacts_keeps_max_artifacts(tmp_path):
    from term_chameleon.watch_live import WATCH_MAX_ARTIFACTS, _prune_artifacts

    for i in range(WATCH_MAX_ARTIFACTS + 10):
        (tmp_path / f"sample-{i:04d}.png").write_bytes(b"x")
        (tmp_path / f"sample-{i:04d}-analysis.png").write_bytes(b"x")
    _prune_artifacts(tmp_path)
    remaining_screens = list(tmp_path.glob("sample-*.png"))
    remaining_screens = [f for f in remaining_screens if "-analysis" not in f.name]
    assert len(remaining_screens) <= WATCH_MAX_ARTIFACTS
    remaining_analysis = list(tmp_path.glob("sample-*-analysis.png"))
    assert len(remaining_analysis) <= WATCH_MAX_ARTIFACTS


def test_analysis_image_path_uses_sips_downsample(monkeypatch, tmp_path):
    source = tmp_path / "sample-0001.png"
    source.write_bytes(b"fake-png")
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        target = Path(command[-1])
        target.write_bytes(b"small-png")

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(watch_live_module.shutil, "which", lambda name: "/usr/bin/sips")
    monkeypatch.setattr(watch_live_module.subprocess, "run", fake_run)
    result = watch_live_module._analysis_image_path(source)
    assert result == tmp_path / "sample-0001-analysis.png"
    assert result.read_bytes() == b"small-png"
    assert calls[0][0] == "/usr/bin/sips"


def test_watch_live_dry_run_switches_after_stable_samples(tmp_path):
    samples = [Sample(0.8), Sample(0.8), Sample(0.8)]

    def provider(index: int, _output_dir: Path, _region):
        return samples[index - 1], f"sample-{index}"

    clock = FakeClock()
    events = run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=2,
            stable=3,
            cooldown=10,
            output_dir=tmp_path,
            dry_run=True,
            initial_mode="balanced",
        ),
        sample_provider=provider,
        sleep=clock.sleep,
        clock=clock,
    )
    assert len(events) == 3
    assert events[-1].switched is True
    assert events[-1].mode == "bright-safe"
    assert events[-1].applied is False
    assert "dry-run" in events[-1].message


def test_watch_live_applies_when_not_dry_run(tmp_path):
    samples = [Sample(0.8)]
    applied = []

    def provider(index: int, _output_dir: Path, _region):
        return samples[index - 1], f"sample-{index}"

    def apply(mode: str) -> LiveApplyResult:
        applied.append(mode)
        return LiveApplyResult(mode, True, ("set_foreground_color",), f"applied {mode}")

    clock = FakeClock()
    events = run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=0.1,
            stable=1,
            cooldown=10,
            output_dir=tmp_path,
            dry_run=False,
            initial_mode="balanced",
        ),
        sample_provider=provider,
        apply_preset=apply,
        sleep=clock.sleep,
        clock=clock,
    )
    assert applied == ["bright-safe"]
    assert events[0].applied is True


def test_watch_live_continues_when_live_apply_fails(tmp_path):
    samples = [Sample(0.8), Sample(0.8)]
    attempted = []

    def provider(index: int, _output_dir: Path, _region):
        return samples[index - 1], f"sample-{index}"

    def apply(mode: str) -> LiveApplyResult:
        attempted.append(mode)
        raise RuntimeError("no current iTerm2 session")

    clock = FakeClock()
    events = run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=1,
            stable=1,
            cooldown=10,
            output_dir=tmp_path,
            dry_run=False,
            initial_mode="balanced",
        ),
        sample_provider=provider,
        apply_preset=apply,
        sleep=clock.sleep,
        clock=clock,
    )
    assert attempted == ["bright-safe"]
    assert len(events) == 2
    assert events[0].switched is True
    assert events[0].applied is False
    assert "apply failed; will continue watching" in events[0].message
    assert events[1].switched is False


def test_watch_live_cooldown_holds_second_switch(tmp_path):
    samples = [Sample(0.8), Sample(0.2)]

    def provider(index: int, _output_dir: Path, _region):
        return samples[index - 1], f"sample-{index}"

    clock = FakeClock()
    events = run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=1,
            stable=1,
            cooldown=10,
            output_dir=tmp_path,
            dry_run=True,
            initial_mode="balanced",
        ),
        sample_provider=provider,
        sleep=clock.sleep,
        clock=clock,
    )
    assert events[0].switched is True
    assert events[0].mode == "bright-safe"
    assert events[1].switched is False
    assert events[1].mode == "bright-safe"
    assert "cooldown active" in events[1].message


def test_watch_live_passes_region_to_sample_provider(tmp_path):
    seen = []

    def provider(_index: int, _output_dir: Path, region):
        seen.append(region)
        return Sample(0.2), "sample"

    clock = FakeClock()
    region = Region(1, 2, 3, 4)
    run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=0.1,
            stable=1,
            cooldown=10,
            output_dir=tmp_path,
            dry_run=True,
            initial_mode="balanced",
            region=region,
        ),
        sample_provider=provider,
        sleep=clock.sleep,
        clock=clock,
    )
    assert seen == [region]


def test_watch_live_waits_for_iterm_window_before_sampling(tmp_path):
    calls = []
    seen_regions = []
    clock = FakeClock()
    region = Region(5, 6, 7, 8)

    def bounds_provider():
        calls.append(clock.now)
        if len(calls) < 3:
            return WindowBoundsResult(False, None, "iTerm2 has no windows")
        return WindowBoundsResult(True, region, "ok")

    def provider(_index: int, _output_dir: Path, sample_region):
        seen_regions.append(sample_region)
        return Sample(0.2), "sample"

    events = run_watch_live(
        WatchLiveConfig(
            interval=1,
            duration=0.1,
            stable=1,
            cooldown=10,
            output_dir=tmp_path,
            dry_run=True,
            initial_mode="balanced",
            iterm_window=True,
        ),
        sample_provider=provider,
        sleep=clock.sleep,
        clock=clock,
        window_bounds_provider=bounds_provider,
    )

    assert len(calls) == 3
    assert seen_regions == [region]
    assert len(events) == 1


def test_watch_live_window_wait_times_out(tmp_path):
    clock = FakeClock()

    def bounds_provider():
        return WindowBoundsResult(False, None, "iTerm2 has no windows")

    try:
        run_watch_live(
            WatchLiveConfig(
                interval=1,
                duration=2,
                stable=1,
                cooldown=10,
                output_dir=tmp_path,
                dry_run=True,
                initial_mode="balanced",
                iterm_window=True,
            ),
            sample_provider=lambda _index, _output_dir, _region: (Sample(0.2), "sample"),
            sleep=clock.sleep,
            clock=clock,
            window_bounds_provider=bounds_provider,
        )
    except RuntimeError as exc:
        assert "after 60.0s" in str(exc)
        assert "iTerm2 has no windows" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
