from __future__ import annotations

from pathlib import Path

from ..config import ConfigError
from ..presets import PRESETS
from ..watch import Sample


def print_decision(decision) -> None:
    print(f"Source: {decision.source}")
    if getattr(decision, "region", None) is not None:
        print(f"Region: {decision.region}")
    print(f"Average luminance: {decision.average_luminance:.3f}")
    print(f"Luminance variance: {decision.luminance_variance:.3f}")
    print(f"Risk: {decision.risk}")
    print(f"Suggested mode: {decision.suggested_mode}")
    print(f"Reason: {decision.reason}")


def require_path(path: Path | None) -> Path:
    if path is None:
        raise ValueError("image path is required")
    return path


def preset_or_error(value: str | None, default: str) -> str:
    resolved = value or default
    if resolved not in PRESETS:
        raise ConfigError(f"unknown preset/mode in config: {resolved!r}")
    return resolved


def parse_sample(raw: str) -> Sample:
    if ":" in raw:
        luminance, variance = raw.split(":", 1)
        return Sample(float(luminance), float(variance))
    return Sample(float(raw), 0.0)


def print_changes(changes) -> None:
    if not changes:
        print("  none")
    for c in changes:
        print(f"- {c.key}: {c.before} -> {c.after}")
        reason = getattr(c, "reason", None)
        if reason:
            print(f"  reason: {reason}")


def print_remaining_failures(remaining, ok_message: str) -> int:
    blocking = [d for d in remaining if d.severity == "fail"]
    if blocking:
        print("\nRemaining failures after proposal:")
        for d in blocking:
            print(f"- {d.code}: {d.message}")
        return 1
    print(f"\n[ok] {ok_message}")
    return 0
