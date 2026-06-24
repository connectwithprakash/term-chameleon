from term_chameleon.cli import main
from term_chameleon.iterm_api import (
    ItermApiEnvironment,
    check_environment,
    live_adapter_script,
    live_adapter_setters,
    write_live_adapter_script,
)


def test_live_adapter_script_compiles_and_contains_session_local_api():
    content = live_adapter_script(preset_name="bright-safe")
    compile(content, "<generated-iterm-live-script>", "exec")
    assert "LocalWriteOnlyProfile" in content
    assert "async_set_profile_properties" in content
    assert "set_background_color" in content
    assert "#090C16" in content


def test_write_live_adapter_script(tmp_path):
    target = write_live_adapter_script(tmp_path / "adapter.py", preset_name="balanced")
    assert target.exists()
    assert target.stat().st_mode & 0o111
    assert "PRESET_NAME = 'balanced'" in target.read_text()


def test_iterm_api_check_cli_reports_environment(capsys):
    status = main(["iterm-api-check"])
    out = capsys.readouterr().out
    env = check_environment()
    assert status == (0 if env.ready_for_live_probe else 1)
    assert "iTerm2 app installed:" in out
    assert "iTerm2 Python package available:" in out
    assert "Python executable:" in out
    assert "required LocalWriteOnlyProfile setters:" in out


def test_iterm_api_check_marks_setters_skipped_when_package_missing(monkeypatch, capsys):
    import term_chameleon.cli as cli

    monkeypatch.setattr(
        cli,
        "check_environment",
        lambda: ItermApiEnvironment(
            app_installed=True,
            python_package_available=False,
            app_paths_checked=("/Applications/iTerm.app",),
            python_executable="/usr/bin/python3",
        ),
    )
    assert main(["iterm-api-check"]) == 1
    out = capsys.readouterr().out
    assert "set_background_color: skipped" in out
    assert "uv sync --extra iterm" in out


def test_live_adapter_setters_are_documented():
    setters = live_adapter_setters()
    assert "set_background_color" in setters
    assert "set_minimum_contrast" in setters
    assert len(setters) >= 10


def test_iterm_live_script_cli_writes_file(tmp_path, capsys):
    output = tmp_path / "live.py"
    assert main(["iterm-live-script", "--preset", "presentation", "--output", str(output)]) == 0
    out = capsys.readouterr().out
    assert "generated iTerm2 live adapter script compiles" in out
    assert output.exists()
    assert "PRESET_NAME = 'presentation'" in output.read_text()
