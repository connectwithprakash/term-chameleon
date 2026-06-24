from __future__ import annotations

from pathlib import Path

from .iterm_profile import dumps_document
from .presets import BALANCED

DEFAULT_DYNAMIC_PROFILES_DIR = (
    Path.home() / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles"
)


def balanced_profile_document(name: str = "Adaptive Glass", guid: str | None = None) -> dict:
    guid = guid or "TERM-CHAMELEON-ADAPTIVE-GLASS"
    p = {
        "Name": name,
        "Guid": guid,
        "Dynamic Profile Parent Name": "Default",
        "Use Separate Colors for Light and Dark Mode": False,
        "Background Color": BALANCED["background"].to_iterm_dict(),
        "Foreground Color": BALANCED["foreground"].to_iterm_dict(),
        "Bold Color": BALANCED["bold"].to_iterm_dict(),
        "Cursor Color": BALANCED["cursor"].to_iterm_dict(),
        "Selection Color": BALANCED["selection"].to_iterm_dict(),
        "Selected Text Color": BALANCED["selected_text"].to_iterm_dict(),
        "Ansi 0 Color": BALANCED["ansi_black"].to_iterm_dict(),
        "Ansi 7 Color": BALANCED["ansi_white"].to_iterm_dict(),
        "Ansi 8 Color": BALANCED["ansi_bright_black"].to_iterm_dict(),
        "Ansi 15 Color": BALANCED["ansi_bright_white"].to_iterm_dict(),
        "Transparency": BALANCED["transparency"],
        "Blur": BALANCED["blur"],
        "Blur Radius": BALANCED["blur_radius"],
        "Minimum Contrast": BALANCED["minimum_contrast"],
    }
    for key in [
        "Background Color",
        "Foreground Color",
        "Bold Color",
        "Cursor Color",
        "Selection Color",
        "Selected Text Color",
        "Ansi 0 Color",
        "Ansi 7 Color",
        "Ansi 8 Color",
        "Ansi 15 Color",
    ]:
        p[key + " (Light)"] = p[key]
        p[key + " (Dark)"] = p[key]
    return {"Profiles": [p]}


def install_balanced_profile(
    *,
    target_dir: Path = DEFAULT_DYNAMIC_PROFILES_DIR,
    name: str = "Adaptive Glass",
    filename: str = "term-chameleon-adaptive-glass.json",
    dry_run: bool = False,
) -> tuple[Path, str]:
    document = balanced_profile_document(name=name)
    content = dumps_document(document)
    target = target_dir / filename
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return target, content
