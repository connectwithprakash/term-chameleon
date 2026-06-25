from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "term-chameleon" / "config.toml"

EXAMPLE_CONFIG = """# Term Chameleon configuration
# Copy to ~/.config/term-chameleon/config.toml and pass --config, or keep as a
# documented baseline for watcher/daemon flags.

[watch]
interval = 2.0
duration = 60.0
stable = 3
cooldown = 10.0
output_dir = "~/Library/Logs/term-chameleon/watch-live-artifacts"
initial_mode = "balanced"
iterm_window = true
# region = "0,0,1440,900"  # Use instead of iterm_window when Accessibility is unavailable.

[daemon]
autolaunch_dir = "~/Library/Application Support/iTerm2/Scripts/AutoLaunch"
log_path = "~/Library/Logs/term-chameleon-watch-live.log"
pid_path = "~/Library/Application Support/term-chameleon/watch-live.pid"
# python = "/path/to/python"
# interval, stable, cooldown, output_dir, initial_mode, iterm_window, and region
# default to [watch] values when omitted here.

[setup]
output_dir = "artifacts/setup"
preset = "balanced"
name = "Adaptive Glass Alpha"
live = false
# profile = "~/Library/Application Support/iTerm2/DynamicProfiles/term-chameleon.json"
"""


class ConfigError(ValueError):
    pass


Config = dict[str, Any]


def load_config(path: str | Path | None) -> Config:
    if path is None:
        return {}
    target = Path(path).expanduser()
    try:
        with target.open("rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {target}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML config {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a table: {target}")
    return data


def section(config: Config, name: str) -> Config:
    raw = config.get(name, {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] must be a table")
    return raw


def value(config_section: Config, key: str, default: Any = None) -> Any:
    return config_section.get(key, default)


def merged_section(config: Config, primary: str, fallback: str | None = None) -> Config:
    base: Config = {}
    if fallback is not None:
        base.update(section(config, fallback))
    base.update(section(config, primary))
    return base


def path_value(raw: Any, default: Path | None = None) -> Path | None:
    if raw is None:
        return default
    if isinstance(raw, Path):
        return raw
    if isinstance(raw, str):
        return Path(raw).expanduser()
    raise ConfigError(f"expected path string, got {type(raw).__name__}")


def bool_value(raw: Any, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    raise ConfigError(f"expected boolean, got {type(raw).__name__}")


def int_value(raw: Any, default: int) -> int:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ConfigError(f"expected integer, got {type(raw).__name__}")
    return raw


def float_value(raw: Any, default: float) -> float:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ConfigError(f"expected number, got {type(raw).__name__}")
    return float(raw)


def str_value(raw: Any, default: str | None = None) -> str | None:
    if raw is None:
        return default
    if isinstance(raw, str):
        return raw
    raise ConfigError(f"expected string, got {type(raw).__name__}")
