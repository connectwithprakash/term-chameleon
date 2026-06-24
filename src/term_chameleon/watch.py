from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Risk = Literal[
    "dark-low-risk",
    "balanced-medium-risk",
    "bright-high-risk",
    "high-variance-high-risk",
    "unknown",
]

RISK_TO_MODE: dict[Risk, str] = {
    "dark-low-risk": "dark-glass",
    "balanced-medium-risk": "balanced",
    "bright-high-risk": "bright-safe",
    "high-variance-high-risk": "high-variance-safe",
    "unknown": "balanced",
}


@dataclass(frozen=True)
class Sample:
    luminance: float
    variance: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.luminance <= 1.0:
            raise ValueError(f"luminance must be between 0 and 1, got {self.luminance!r}")
        if self.variance < 0.0:
            raise ValueError(f"variance must be non-negative, got {self.variance!r}")


@dataclass(frozen=True)
class Classification:
    sample: Sample
    risk: Risk
    mode: str
    reason: str


def classify_sample(sample: Sample) -> Classification:
    if sample.variance >= 0.08:
        risk: Risk = "high-variance-high-risk"
        reason = f"variance {sample.variance:.2f} >= 0.08"
    elif sample.luminance > 0.65:
        risk = "bright-high-risk"
        reason = f"luminance {sample.luminance:.2f} > 0.65"
    elif sample.luminance < 0.35:
        risk = "dark-low-risk"
        reason = f"luminance {sample.luminance:.2f} < 0.35"
    else:
        risk = "balanced-medium-risk"
        reason = f"luminance {sample.luminance:.2f} in balanced range"
    return Classification(sample=sample, risk=risk, mode=RISK_TO_MODE[risk], reason=reason)


@dataclass
class ModeSelector:
    current_mode: str = "balanced"
    stable_samples_required: int = 3
    min_luminance_delta: float = 0.10

    def __post_init__(self) -> None:
        if self.stable_samples_required < 1:
            raise ValueError("stable_samples_required must be >= 1")
        self._candidate_mode: str | None = None
        self._candidate_count = 0
        self._last_switch_luminance: float | None = None

    def observe(self, sample: Sample) -> tuple[str, Classification, bool]:
        classification = classify_sample(sample)
        candidate = classification.mode
        if candidate == self.current_mode:
            self._candidate_mode = None
            self._candidate_count = 0
            return self.current_mode, classification, False

        if self._last_switch_luminance is not None:
            delta = abs(sample.luminance - self._last_switch_luminance)
            if delta < self.min_luminance_delta:
                return self.current_mode, classification, False

        if self._candidate_mode != candidate:
            self._candidate_mode = candidate
            self._candidate_count = 1
        else:
            self._candidate_count += 1

        if self._candidate_count >= self.stable_samples_required:
            self.current_mode = candidate
            self._last_switch_luminance = sample.luminance
            self._candidate_mode = None
            self._candidate_count = 0
            return self.current_mode, classification, True
        return self.current_mode, classification, False


def simulate_modes(
    samples: list[Sample], selector: ModeSelector | None = None
) -> list[tuple[str, str, bool]]:
    selector = selector or ModeSelector()
    events = []
    for sample in samples:
        mode, classification, switched = selector.observe(sample)
        events.append((classification.risk, mode, switched))
    return events
