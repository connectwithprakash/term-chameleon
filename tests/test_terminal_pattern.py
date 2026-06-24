from term_chameleon.cli import main
from term_chameleon.terminal_pattern import (
    shell_script_content,
    write_pattern_bundle,
    write_pattern_script,
)


def test_shell_script_content_contains_ansi_pattern():
    content = shell_script_content()
    assert content.startswith("#!/usr/bin/env bash")
    assert "printf '%b'" in content
    assert "Term Chameleon pattern rendered" in content


def test_write_pattern_script(tmp_path):
    path = write_pattern_script(tmp_path / "render.sh")
    assert path.exists()
    assert path.stat().st_mode & 0o111


def test_write_pattern_bundle(tmp_path):
    pattern, script = write_pattern_bundle(tmp_path)
    assert pattern.exists()
    assert script.exists()
    assert "ansi-15 bright white" in pattern.read_text()


def test_pattern_script_cli(tmp_path, capsys):
    assert main(["pattern-script", "--output-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "generated ANSI terminal pattern artifacts" in out
    assert (tmp_path / "render-pattern.sh").exists()
