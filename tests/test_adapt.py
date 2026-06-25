import shutil

from term_chameleon.adapt import adapt_profile_from_image, decide_from_image
from term_chameleon.cli import main
from term_chameleon.color import Color
from term_chameleon.images import RasterImage, Region, solid_image, write_ppm

FIXTURE = "tests/fixtures/iterm/good-dark-glass.json"


def test_decide_from_image_suggests_bright_safe_for_light_image(tmp_path):
    image = write_ppm(tmp_path / "light.ppm", solid_image(8, 8, Color.from_hex("#FFFFFF")))
    decision = decide_from_image(image)
    assert decision.risk == "bright-high-risk"
    assert decision.suggested_mode == "bright-safe"


def test_decide_from_image_region_uses_only_selected_pixels(tmp_path):
    image = write_ppm(
        tmp_path / "mixed.ppm",
        RasterImage(
            2,
            1,
            (Color.from_hex("#000000"), Color.from_hex("#FFFFFF")),
        ),
    )
    decision = decide_from_image(image, region=Region(1, 0, 1, 1))
    assert decision.region == Region(1, 0, 1, 1)
    assert decision.suggested_mode == "bright-safe"


def test_adapt_profile_from_image_dry_run(tmp_path):
    profile = tmp_path / "profile.json"
    shutil.copy(FIXTURE, profile)
    image = write_ppm(tmp_path / "light.ppm", solid_image(8, 8, Color.from_hex("#FFFFFF")))
    decision = adapt_profile_from_image(image, profile, dry_run=True)
    assert decision.suggested_mode == "bright-safe"
    assert decision.mode_result is not None
    changes, _remaining = decision.mode_result
    assert any(change.key == "Foreground Color" for change in changes)


def test_sample_cli_from_image(tmp_path, capsys):
    image = write_ppm(tmp_path / "dark.ppm", solid_image(8, 8, Color.from_hex("#000000")))
    assert main(["sample", "--image", str(image)]) == 0
    out = capsys.readouterr().out
    assert "Suggested mode: dark-glass" in out


def test_sample_cli_from_image_region(tmp_path, capsys):
    image = write_ppm(
        tmp_path / "mixed.ppm",
        RasterImage(
            2,
            1,
            (Color.from_hex("#000000"), Color.from_hex("#FFFFFF")),
        ),
    )
    assert main(["sample", "--image", str(image), "--region", "1,0,1,1"]) == 0
    out = capsys.readouterr().out
    assert "Region: 1,0,1,1" in out
    assert "Suggested mode: bright-safe" in out


def test_sample_cli_rejects_iterm_window_with_image(tmp_path, capsys):
    image = write_ppm(tmp_path / "dark.ppm", solid_image(8, 8, Color.from_hex("#000000")))
    assert main(["sample", "--image", str(image), "--iterm-window"]) == 2
    assert "--iterm-window requires --screen" in capsys.readouterr().err


def test_adapt_once_cli_refuses_write_without_yes(tmp_path, capsys):
    profile = tmp_path / "profile.json"
    shutil.copy(FIXTURE, profile)
    image = write_ppm(tmp_path / "light.ppm", solid_image(8, 8, Color.from_hex("#FFFFFF")))
    assert main(["adapt-once", str(profile), "--image", str(image)]) == 2
    assert "Refusing to write" in capsys.readouterr().err


def test_adapt_once_cli_dry_run(tmp_path, capsys):
    profile = tmp_path / "profile.json"
    shutil.copy(FIXTURE, profile)
    image = write_ppm(tmp_path / "light.ppm", solid_image(8, 8, Color.from_hex("#FFFFFF")))
    assert main(["adapt-once", str(profile), "--image", str(image), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Suggested mode: bright-safe" in out
    assert "Planned changes:" in out
