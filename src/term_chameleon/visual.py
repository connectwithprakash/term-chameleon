from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .color import Color
from .contrast import contrast_ratio
from .iterm_profile import ItermProfile, load_profile


@dataclass(frozen=True)
class VisualCheck:
    background: str
    style: str
    foreground: str
    effective_background: str
    contrast: float
    threshold: float

    @property
    def passed(self) -> bool:
        return self.contrast >= self.threshold


CONTROLLED_BACKGROUNDS = {
    "solid-dark": Color.from_hex("#000000"),
    "solid-light": Color.from_hex("#FFFFFF"),
    "mid-gray": Color.from_hex("#808080"),
    "warm-light": Color.from_hex("#F2E8D5"),
}


def simulate_visual_checks(profile: ItermProfile) -> list[VisualCheck]:
    terminal_bg = profile.background or Color.from_hex("#000000")
    transparency = profile.transparency() or 0.0
    terminal_alpha = max(0.0, min(1.0, 1.0 - transparency))
    terminal_surface = Color(terminal_bg.r, terminal_bg.g, terminal_bg.b, terminal_alpha)
    styles = {
        "normal": (profile.color("Foreground Color"), 4.5),
        "bold": (profile.color("Bold Color"), 4.5),
        "ansi-black": (profile.color("Ansi 0 Color"), 3.0),
        "ansi-bright-black": (profile.color("Ansi 8 Color"), 3.0),
        "ansi-white": (profile.color("Ansi 7 Color"), 4.5),
        "ansi-bright-white": (profile.color("Ansi 15 Color"), 4.5),
    }
    checks: list[VisualCheck] = []
    for bg_name, behind in CONTROLLED_BACKGROUNDS.items():
        effective_bg = terminal_surface.blend_over(behind)
        for style, (fg, threshold) in styles.items():
            if fg is None:
                continue
            checks.append(
                VisualCheck(
                    background=bg_name,
                    style=style,
                    foreground=fg.to_hex(),
                    effective_background=effective_bg.to_hex(),
                    contrast=contrast_ratio(fg, effective_bg),
                    threshold=threshold,
                )
            )
    return checks


def write_visual_report(
    profile_path: str | Path, output_dir: str | Path
) -> tuple[Path, Path, list[VisualCheck]]:
    profile = load_profile(profile_path)
    checks = simulate_visual_checks(profile)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "report.json"
    md_path = out / "report.md"
    json_path.write_text(
        json.dumps([asdict(c) | {"passed": c.passed} for c in checks], indent=2) + "\n",
        encoding="utf-8",
    )
    rows = [
        "# Term Chameleon Visual Simulation Report",
        "",
        "This is a deterministic pre-screenshot visual risk simulation. It models the terminal "
        "background blended over controlled solid backgrounds and computes WCAG contrast.",
        "",
        "| Background | Style | FG | Effective BG | Contrast | Threshold | Result |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for c in checks:
        rows.append(
            f"| {c.background} | {c.style} | {c.foreground} | {c.effective_background} | "
            f"{c.contrast:.2f}:1 | {c.threshold:.1f}:1 | {'PASS' if c.passed else 'FAIL'} |"
        )
    md_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return json_path, md_path, checks
