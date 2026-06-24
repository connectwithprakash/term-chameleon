from term_chameleon.background_html import (
    BACKGROUND_CSS,
    render_background_html,
    write_background_html,
)
from term_chameleon.cli import main


def test_render_background_html_contains_name_and_css():
    html = render_background_html("solid-dark", "#050814")
    assert "solid-dark" in html
    assert "#050814" in html
    assert "term-chameleon background" in html


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
