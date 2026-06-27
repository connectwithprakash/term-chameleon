from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .presets import PRESETS

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
interval = 10.0  # Daemon default favors low overhead over rapid adaptation.
iterm_window = false  # Keep daemon startup robust; set true to scope daemon sampling to iTerm2.
# region = "0,0,1440,900"
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


@dataclass(frozen=True)
class ConfigValidation:
    path: str | None
    sections: list[str]
    errors: list[str]
    warnings: list[str]

    @property
    def passed(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["passed"] = self.passed
        return data


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


KNOWN_SECTIONS = {"watch", "daemon", "setup"}
COMMON_WATCH_KEYS = {
    "interval",
    "duration",
    "stable",
    "cooldown",
    "output_dir",
    "initial_mode",
    "iterm_window",
    "region",
}
DAEMON_WATCH_KEYS = COMMON_WATCH_KEYS - {"duration"}
KNOWN_SECTION_KEYS = {
    "watch": COMMON_WATCH_KEYS,
    "daemon": DAEMON_WATCH_KEYS | {"autolaunch_dir", "log_path", "pid_path", "python"},
    "setup": {"output_dir", "preset", "name", "live", "profile"},
}


def validate_config(config: Config, *, path: str | Path | None = None) -> ConfigValidation:
    errors: list[str] = []
    warnings: list[str] = []
    sections_present = sorted(name for name, raw in config.items() if isinstance(raw, dict))

    for name in config:
        if name not in KNOWN_SECTIONS:
            errors.append(f"unknown top-level section [{name}]")

    sections: dict[str, Config] = {}
    for name in KNOWN_SECTIONS:
        try:
            sections[name] = section(config, name)
        except ConfigError as exc:
            errors.append(str(exc))
            sections[name] = {}

    for section_name, section_data in sections.items():
        _check_unknown_keys(section_name, section_data, errors)

    _validate_watch_like_section(
        "watch", sections["watch"], errors, warnings, include_duration=True
    )
    _validate_watch_like_section(
        "daemon", sections["daemon"], errors, warnings, include_duration=False
    )
    _validate_path("daemon", sections["daemon"], "autolaunch_dir", errors)
    _validate_path("daemon", sections["daemon"], "log_path", errors)
    _validate_path("daemon", sections["daemon"], "pid_path", errors)
    _validate_string("daemon", sections["daemon"], "python", errors)

    _validate_path("setup", sections["setup"], "output_dir", errors)
    _validate_path("setup", sections["setup"], "profile", errors)
    _validate_preset("setup", sections["setup"], "preset", errors)
    _validate_string("setup", sections["setup"], "name", errors)
    _validate_bool("setup", sections["setup"], "live", errors)

    return ConfigValidation(
        path=str(Path(path).expanduser()) if path is not None else None,
        sections=sections_present,
        errors=errors,
        warnings=warnings,
    )


def _check_unknown_keys(section_name: str, data: Config, errors: list[str]) -> None:
    known = KNOWN_SECTION_KEYS[section_name]
    for key in sorted(data):
        if key not in known:
            errors.append(f"unknown key [{section_name}].{key}")


def _validate_watch_like_section(
    section_name: str,
    data: Config,
    errors: list[str],
    warnings: list[str],
    *,
    include_duration: bool,
) -> None:
    _validate_float(section_name, data, "interval", errors, minimum=0.0, exclusive_minimum=True)
    if include_duration:
        _validate_float(section_name, data, "duration", errors, minimum=0.0, exclusive_minimum=True)
    _validate_int(section_name, data, "stable", errors, minimum=1)
    _validate_float(section_name, data, "cooldown", errors, minimum=0.0)
    _validate_path(section_name, data, "output_dir", errors)
    _validate_preset(section_name, data, "initial_mode", errors)
    _validate_bool(section_name, data, "iterm_window", errors)
    _validate_region(section_name, data, "region", errors)
    if data.get("region") is not None and data.get("iterm_window") is True:
        warnings.append(
            f"[{section_name}] defines both region and iterm_window=true; region takes precedence"
        )


def _validate_path(section_name: str, data: Config, key: str, errors: list[str]) -> None:
    if key in data:
        _capture_error(errors, section_name, key, lambda: path_value(data[key]))


def _validate_bool(section_name: str, data: Config, key: str, errors: list[str]) -> None:
    if key in data:
        _capture_error(errors, section_name, key, lambda: bool_value(data[key]))


def _validate_int(
    section_name: str,
    data: Config,
    key: str,
    errors: list[str],
    *,
    minimum: int | None = None,
) -> None:
    if key not in data:
        return
    before = len(errors)
    _capture_error(errors, section_name, key, lambda: int_value(data[key], 0))
    if len(errors) != before:
        return
    parsed = int_value(data[key], 0)
    if minimum is not None and parsed < minimum:
        errors.append(f"[{section_name}].{key}: expected integer >= {minimum}")


def _validate_float(
    section_name: str,
    data: Config,
    key: str,
    errors: list[str],
    *,
    minimum: float | None = None,
    exclusive_minimum: bool = False,
) -> None:
    if key not in data:
        return
    before = len(errors)
    _capture_error(errors, section_name, key, lambda: float_value(data[key], 0.0))
    if len(errors) != before:
        return
    parsed = float_value(data[key], 0.0)
    if minimum is None:
        return
    if exclusive_minimum and parsed <= minimum:
        errors.append(f"[{section_name}].{key}: expected number > {minimum:g}")
    elif not exclusive_minimum and parsed < minimum:
        errors.append(f"[{section_name}].{key}: expected number >= {minimum:g}")


def _validate_string(section_name: str, data: Config, key: str, errors: list[str]) -> None:
    if key in data:
        _capture_error(errors, section_name, key, lambda: str_value(data[key]))


def _validate_preset(section_name: str, data: Config, key: str, errors: list[str]) -> None:
    if key not in data:
        return
    raw = data[key]
    try:
        parsed = str_value(raw)
    except ConfigError as exc:
        errors.append(f"[{section_name}].{key}: {exc}")
        return
    if parsed not in PRESETS:
        errors.append(f"[{section_name}].{key}: unknown preset/mode {parsed!r}")


def _validate_region(section_name: str, data: Config, key: str, errors: list[str]) -> None:
    if key not in data:
        return
    raw = data[key]
    try:
        parsed = str_value(raw)
    except ConfigError as exc:
        errors.append(f"[{section_name}].{key}: {exc}")
        return
    if parsed is None:
        errors.append(f"[{section_name}].{key}: expected string")
        return
    parts = parsed.split(",")
    if len(parts) != 4:
        errors.append(f"[{section_name}].{key}: expected x,y,width,height")
        return
    try:
        x, y, width, height = [int(part.strip()) for part in parts]
    except ValueError:
        errors.append(f"[{section_name}].{key}: expected integer x,y,width,height")
        return
    if width <= 0 or height <= 0:
        errors.append(f"[{section_name}].{key}: width and height must be positive")
    if x < 0 or y < 0:
        errors.append(f"[{section_name}].{key}: x and y must be nonnegative")


def _capture_error(errors: list[str], section_name: str, key: str, fn: Any) -> None:
    try:
        fn()
    except ConfigError as exc:
        errors.append(f"[{section_name}].{key}: {exc}")
