from term_chameleon.iterm_connection import ItermConnectionProbe, probe_iterm_connection


def test_probe_iterm_connection_returns_structured_result():
    result = probe_iterm_connection()
    assert isinstance(result.connected, bool)
    assert isinstance(result.message, str)
    assert result.message


def test_iterm_connect_probe_cli_with_monkeypatch(monkeypatch, capsys):
    import term_chameleon.cli as cli

    monkeypatch.setattr(
        cli,
        "probe_iterm_connection",
        lambda: ItermConnectionProbe(True, "connected"),
    )
    assert cli.main(["iterm-connect-probe"]) == 0
    assert "connected to live iTerm2 Python API" in capsys.readouterr().out
