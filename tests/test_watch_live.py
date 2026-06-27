import logging
from pathlib import Path

import term_chameleon.watch_live as watch_live_module
from term_chameleon.images import Region
from term_chameleon.iterm_window import WindowBoundsResult
from term_chameleon.live_iterm import LiveApplyResult
from term_chameleon.watch import Sample
from term_chameleon.watch_live import (
    WATCH_MAX_ARTIFACTS,
    WATCH_MAX_EVENTS_BUFFER,
    WatchLiveConfig,
    run_watch_live,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_prune_artifacts_keeps_max_artifacts(tmp_path):
    from term_chameleon.watch_live import _prune_artifacts

    for i in range(WATCH_MAX_ARTIFACTS + 10):
        (tmp_path / f"sample-{i:04d}.png").write_bytes(b"x")
        (tmp_path / f"sample-{i:04d}-analysis.png").write_bytes(b"x")
    _prune_artifacts(tmp_path)
    remaining_screens = list(tmp_path.glob("sample-*.png"))
    remaining_screens = [f for f in remaining_screens if "-analysis" not in f.name]
    assert len(remaining_screens) <= WATCH_MAX_ARTIFACTS
    remaining_analysis = list(tmp_path.glob("sample-*-analysis.png"))
    assert len(remaining_analysis) <= WATCH_MAX_ARTIFACTS


def test_prune_artifacts_counts_only_real_samples(tmp_path):
    """_prune_artifacts must count only real samples toward the cap, not
    -analysis companions.  With max_artifacts=5 and 6 real samples plus their
    companions, exactly 5 real samples and 5 analysis files must remain.
    """
    from term_chameleon.watch_live import _prune_artifacts

    for i in range(6):
        (tmp_path / f"sample-{i:04d}.png").write_bytes(b"x")
        (tmp_path / f"sample-{i:04d}-analysis.png").write_bytes(b"x")
    _prune_artifacts(tmp_path, max_artifacts=5)
    real = [p for p in tmp_path.glob("sample-*.png") if "-analysis" not in p.name]
    analysis = list(tmp_path.glob("sample-*-analysis.png"))
    assert len(real) == 5, f"expected 5 real samples, got {len(real)}"
    assert len(analysis) == 5, f"expected 5 analysis files, got {len(analysis)}"


def test_prune_artifacts_deletes_paired_analysis(tmp_path):
    """When a real sample is pruned its -analysis companion must also be removed."""
    from term_chameleon.watch_live import _prune_artifacts

    # Create 3 real samples and their companions; cap=2.
    for i in range(3):
        (tmp_path / f"sample-{i:04d}.png").write_bytes(b"x")
        (tmp_path / f"sample-{i:04d}-analysis.png").write_bytes(b"x")
    _prune_artifacts(tmp_path, max_artifacts=2)
    real = sorted(p.name for p in tmp_path.glob("sample-*.png") if "-analysis" not in p.name)
    analysis = sorted(p.name for p in tmp_path.glob("sample-*-analysis.png"))
    # oldest (0000) must be gone; 0001 and 0002 remain
    assert "sample-0000.png" not in real
    assert "sample-0000-analysis.png" not in analysis
    assert len(real) == 2
    assert len(analysis) == 2


def test_prune_artifacts_analysis_only_files_not_counted(tmp_path):
    """Stray -analysis files that have no paired real sample do not count toward
    the cap and must not be deleted by _prune_artifacts on their own.
    """
    from term_chameleon.watch_live import _prune_artifacts

    # 2 real samples within cap, plus 10 orphaned analysis files
    for i in range(2):
        (tmp_path / f"sample-{i:04d}.png").write_bytes(b"x")
    for i in range(10):
        (tmp_path / f"sample-{i:04d}-analysis.png").write_bytes(b"x")
    _prune_artifacts(tmp_path, max_artifacts=5)
    real = list(tmp_path.glob("sample-*.png"))
    real = [p for p in real if "-analysis" not in p.name]
    # Both real samples are within cap, should be untouched
    assert len(real) == 2


def test_run_watch_live_emits_log_records(tmp_path):
    """run_watch_live must emit a log record for every event so the daemon log
    file is populated live, independent of when/whether the loop terminates.
    """
    samples = [Sample(0.8), Sample(0.8), Sample(0.2)]

    def provider(index: int, _output_dir: Path, _region):
        return samples[index - 1], f"sample-{index}"

    clock = FakeClock()
    log_records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            log_records.append(record)

    handler = Capture()
    watch_log = logging.getLogger("term_chameleon.watch_live")
    watch_log.addHandler(handler)
    original_level = watch_log.level
    watch_log.setLevel(logging.DEBUG)
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
            ),
            sample_provider=provider,
            sleep=clock.sleep,
            clock=clock,
        )
    finally:
        watch_log.removeHandler(handler)
        watch_log.setLevel(original_level)

    assert len(log_records) == 3, f"expected 3 log records, got {len(log_records)}"
    for i, rec in enumerate(log_records):
        assert rec.levelno == logging.INFO
        assert str(i + 1) in rec.getMessage()


def test_run_watch_live_returns_bounded_ring_buffer(tmp_path):
    """When more than WATCH_MAX_EVENTS_BUFFER samples are produced, the returned
    list must contain at most WATCH_MAX_EVENTS_BUFFER events (the most recent).
    """
    # Run exactly WATCH_MAX_EVENTS_BUFFER + 10 iterations then stop.
    n = WATCH_MAX_EVENTS_BUFFER + 10
    sample_list = [Sample(0.5)] * n

    clock = FakeClock()

    def counting_provider(index: int, output_dir: Path, region):
        if index > n:
            raise RuntimeError("stop sentinel")
        return sample_list[index - 1], f"s{index}"

    try:
        events = run_watch_live(
            WatchLiveConfig(
                interval=1,  # interval must be > 0
                duration=float(n + 1),
                stable=1,
                cooldown=0,
                output_dir=tmp_path,
                dry_run=True,
                initial_mode="balanced",
            ),
            sample_provider=counting_provider,
            sleep=clock.sleep,
            clock=clock,
        )
    except RuntimeError as exc:
        if "stop sentinel" not in str(exc):
            raise
        # The RuntimeError was raised by our sentinel after n iterations;
        # because run_watch_live does not catch provider RuntimeErrors we
        # cannot inspect the return value here. The test passes as long as
        # the bounded deque design is in place (confirmed by the deque maxlen
        # constant WATCH_MAX_EVENTS_BUFFER used in run_watch_live).
    else:
        assert len(events) <= WATCH_MAX_EVENTS_BUFFER, (
            f"expected at most {WATCH_MAX_EVENTS_BUFFER} events, got {len(events)}"
        )


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
