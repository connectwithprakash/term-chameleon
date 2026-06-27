from __future__ import annotations

import html
import subprocess
from dataclasses import dataclass
from pathlib import Path

BACKGROUND_CSS: dict[str, str] = {
    "solid-dark": "#050814",
    "solid-light": "#F8FAFC",
    "mid-gray": "#808080",
    "checkerboard": "repeating-conic-gradient(#050814 0% 25%, #F8FAFC 0% 50%) 0 0 / 64px 64px",
    "gradient": "linear-gradient(90deg, #050814, #F8FAFC)",
}


@dataclass(frozen=True)
class HtmlBackgroundArtifact:
    name: str
    path: Path


def render_background_html(name: str, css_background: str) -> str:
    if css_background not in BACKGROUND_CSS.values():
        raise ValueError(
            f"css_background must be a known BACKGROUND_CSS value; got {css_background!r}"
        )
    escaped_name = html.escape(name)
    escaped_background = css_background.replace("</", "<\\/")
    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Term Chameleon Background: {escaped_name}</title>
<style>
  html, body {{
    margin: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }}
  body {{
    background: {escaped_background};
  }}
  .label {{
    position: fixed;
    left: 24px;
    bottom: 24px;
    padding: 8px 12px;
    border-radius: 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 14px;
    color: #E5EBF5;
    background: rgba(0, 0, 0, 0.55);
  }}
</style>
</head>
<body>
<div class=\"label\">term-chameleon background: {escaped_name}</div>
</body>
</html>
"""


def write_background_html(output_dir: str | Path) -> list[HtmlBackgroundArtifact]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for name, css in BACKGROUND_CSS.items():
        path = out / f"{name}.html"
        path.write_text(render_background_html(name, css), encoding="utf-8")
        artifacts.append(HtmlBackgroundArtifact(name=name, path=path))
    index = out / "index.html"
    index.write_text(render_index(artifacts), encoding="utf-8")
    artifacts.append(HtmlBackgroundArtifact(name="index", path=index))
    return artifacts


def render_index(artifacts: list[HtmlBackgroundArtifact]) -> str:
    links = "\n".join(
        f'<li><a href="{html.escape(artifact.path.name)}">{html.escape(artifact.name)}</a></li>'
        for artifact in artifacts
    )
    return f"""<!doctype html>
<html lang=\"en\">
<head><meta charset=\"utf-8\"><title>Term Chameleon Backgrounds</title></head>
<body>
<h1>Term Chameleon Backgrounds</h1>
<ul>
{links}
</ul>
</body>
</html>
"""


def open_file(path: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["open", str(Path(path))], check=False, text=True, capture_output=True)
