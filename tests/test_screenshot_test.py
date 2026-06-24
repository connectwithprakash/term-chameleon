import json

from term_chameleon.cli import main
from term_chameleon.screenshot_test import (
    analyze_image_file,
    generate_background_artifacts,
    run_screenshot_test,
)


def test_generate_background_artifacts(tmp_path):
    artifacts = generate_background_artifacts(tmp_path, width=64, height=32)
    names = {artifact.name for artifact in artifacts}
    assert names == {"solid-dark", "solid-light", "mid-gray", "checkerboard", "gradient"}
    assert all(artifact.path.exists() for artifact in artifacts)
    by_name = {artifact.name: artifact for artifact in artifacts}
    assert by_name["solid-dark"].suggested_mode == "dark-glass"
    assert by_name["solid-light"].suggested_mode == "bright-safe"
    assert by_name["checkerboard"].suggested_mode == "high-variance-safe"


def test_run_screenshot_test_writes_reports_without_capture(tmp_path):
    report = run_screenshot_test(tmp_path, capture=False, width=64, height=32)
    assert report.screenshot is None
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
    data = json.loads((tmp_path / "report.json").read_text())
    assert len(data["backgrounds"]) == 5
    assert data["screenshot"] is None
    assert data["screenshot_stats"] is None


def test_analyze_image_file_supports_ppm(tmp_path):
    artifacts = generate_background_artifacts(tmp_path, width=8, height=8)
    dark = next(artifact for artifact in artifacts if artifact.name == "solid-dark")
    stats = analyze_image_file(dark.path)
    assert stats.average_luminance < 0.01


def test_screenshot_test_cli_without_capture(tmp_path, capsys):
    assert (
        main(
            [
                "screenshot-test",
                "--output-dir",
                str(tmp_path),
                "--width",
                "32",
                "--height",
                "16",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "screenshot-test foundation passed" in out
    assert (tmp_path / "backgrounds" / "checkerboard.ppm").exists()
