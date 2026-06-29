from term_chameleon.cli import main
from term_chameleon.watch_live import WatchLiveEvent


def test_watch_live_cli_refuses_without_yes_or_dry_run(capsys):
    assert main(["watch-live", "--duration", "0.1"]) == 2
    assert "Refusing to mutate iTerm2" in capsys.readouterr().err


def test_watch_live_cli_refuses_with_clear_error_on_non_iterm2(monkeypatch, capsys):
    """watch-live --yes on a non-iTerm2 terminal must exit 2 with a clear message
    instead of looping with silent apply failures (the old no-op behaviour)."""
    # Simulate a Kitty terminal by clearing iTerm2 env vars and setting Kitty's.
    monkeypatch.setenv("TERM_PROGRAM", "kitty")
    monkeypatch.delenv("TERM", raising=False)
    # Ensure the iTerm2 marker is absent.
    assert main(["watch-live", "--yes", "--duration", "0.1"]) == 2
    err = capsys.readouterr().err
    assert "iTerm2" in err
    assert "osc apply" in err


def test_watch_live_dry_run_skips_terminal_check(monkeypatch, capsys):
    """--dry-run must bypass the terminal-type guard (it never calls the live API)."""
    import term_chameleon.cli as cli

    monkeypatch.setenv("TERM_PROGRAM", "kitty")

    def fake_run(config, **_kwargs):
        return []

    monkeypatch.setattr(cli, "run_watch_live", fake_run)
    assert main(["watch-live", "--dry-run", "--duration", "0.1"]) == 0


def test_watch_live_demo_cycle_refuses_on_non_iterm2(monkeypatch, capsys):
    """--demo-cycle --yes must fail on non-iTerm2 with a clear message instead of
    silently looping without applying any colors (demo_cycle uses the same iTerm2
    apply path as the normal live path)."""
    monkeypatch.setenv("TERM_PROGRAM", "kitty")
    monkeypatch.delenv("TERM", raising=False)
    assert main(["watch-live", "--yes", "--demo-cycle", "--duration", "0.1"]) == 2
    err = capsys.readouterr().err
    assert "iTerm2" in err
    assert "osc apply" in err


def test_watch_live_cli_dry_run_with_monkeypatch(monkeypatch, capsys):
    import term_chameleon.cli as cli

    def fake_run(config):
        assert config.dry_run is True
        return [
            WatchLiveEvent(
                index=1,
                elapsed=0.0,
                luminance=0.8,
                variance=0.0,
                risk="bright-high-risk",
                mode="bright-safe",
                candidate_mode="bright-safe",
                switched=True,
                applied=False,
                reason="test",
                message="dry-run would apply bright-safe",
            )
        ]

    monkeypatch.setattr(cli, "run_watch_live", fake_run)
    assert main(["watch-live", "--dry-run", "--duration", "0.1"]) == 0
    out = capsys.readouterr().out
    assert "watch-live completed 1 sample" in out
    assert "bright-safe" in out
