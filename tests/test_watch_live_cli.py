from term_chameleon.cli import main
from term_chameleon.watch_live import WatchLiveEvent


def test_watch_live_cli_refuses_without_yes_or_dry_run(capsys):
    assert main(["watch-live", "--duration", "0.1"]) == 2
    assert "Refusing to mutate iTerm2" in capsys.readouterr().err


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
