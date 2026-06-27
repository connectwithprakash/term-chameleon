import sys
import time
import types

from term_chameleon.iterm_connection import ItermConnectionProbe, probe_iterm_connection


def test_probe_iterm_connection_returns_structured_result():
    result = probe_iterm_connection()
    assert isinstance(result.connected, bool)
    assert isinstance(result.message, str)
    assert result.message


def test_probe_iterm_connection_times_out_on_unresponsive_daemon(monkeypatch):
    """A hung iterm2.run_until_complete must not block the probe indefinitely."""
    fake = types.ModuleType("iterm2")

    def hang(_main):
        time.sleep(30)  # simulate an unresponsive daemon; should be abandoned by timeout

    fake.run_until_complete = hang
    fake.async_get_app = None
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    start = time.monotonic()
    result = probe_iterm_connection(timeout=0.2)
    elapsed = time.monotonic() - start

    assert result.connected is False
    assert "timed out" in result.message
    assert elapsed < 5  # returned promptly rather than waiting out the 30s sleep


def test_iterm_connect_probe_cli_with_monkeypatch(monkeypatch, capsys):
    import term_chameleon.cli as cli

    monkeypatch.setattr(
        cli,
        "probe_iterm_connection",
        lambda: ItermConnectionProbe(True, "connected"),
    )
    assert cli.main(["iterm-connect-probe"]) == 0
    assert "connected to live iTerm2 Python API" in capsys.readouterr().out
