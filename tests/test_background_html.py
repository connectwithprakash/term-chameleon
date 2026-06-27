import subprocess
from unittest.mock import patch

import pytest

from term_chameleon.background_html import (
    BACKGROUND_CSS,
    open_file,
    render_background_html,
    write_background_html,
)
from term_chameleon.cli import main


def test_render_background_html_contains_name_and_css():
    html = render_background_html("solid-dark", "#050814")
    assert "solid-dark" in html
    assert "#050814" in html
    assert "term-chameleon background" in html


def test_render_background_html_rejects_unknown_css():
    """render_background_html raises ValueError for css_background outside BACKGROUND_CSS."""
    with pytest.raises(ValueError, match="known BACKGROUND_CSS value"):
        render_background_html("custom", "red")


def test_write_background_html(tmp_path):
    artifacts = write_background_html(tmp_path)
    names = {artifact.name for artifact in artifacts}
    assert set(BACKGROUND_CSS) <= names
    assert "index" in names
    assert (tmp_path / "checkerboard.html").exists()
    assert "checkerboard" in (tmp_path / "index.html").read_text()


def test_background_html_cli(tmp_path, capsys):
    assert main(["background-html", "--output-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "generated controlled HTML backgrounds" in out
    assert (tmp_path / "gradient.html").exists()


# ---------------------------------------------------------------------------
# open_file — timeout behaviour
# ---------------------------------------------------------------------------


def test_open_file_passes_timeout_to_subprocess(tmp_path):
    """open_file must forward the timeout to subprocess.run."""
    dummy = tmp_path / "index.html"
    dummy.write_text("<html/>", encoding="utf-8")

    captured: list[dict] = []

    def fake_run(*args, **kwargs):
        captured.append(kwargs)
        return subprocess.CompletedProcess(args[0], returncode=0, stdout="", stderr="")

    with patch("term_chameleon.background_html.subprocess.run", side_effect=fake_run):
        open_file(dummy, timeout=7.0)

    assert captured, "subprocess.run was not called"
    assert captured[0].get("timeout") == 7.0


def test_open_file_default_timeout_is_ten_seconds(tmp_path):
    """Default timeout for open_file must be 10.0 seconds."""
    dummy = tmp_path / "index.html"
    dummy.write_text("<html/>", encoding="utf-8")

    captured: list[dict] = []

    def fake_run(*args, **kwargs):
        captured.append(kwargs)
        return subprocess.CompletedProcess(args[0], returncode=0, stdout="", stderr="")

    with patch("term_chameleon.background_html.subprocess.run", side_effect=fake_run):
        open_file(dummy)

    assert captured[0].get("timeout") == 10.0


def test_open_file_timeout_raises_runtime_error(tmp_path):
    """When `open` times out, open_file must raise RuntimeError (not TimeoutExpired)."""
    dummy = tmp_path / "index.html"
    dummy.write_text("<html/>", encoding="utf-8")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 10))

    with (
        patch("term_chameleon.background_html.subprocess.run", side_effect=fake_run),
        pytest.raises(RuntimeError, match="timed out"),
    ):
        open_file(dummy, timeout=10.0)
