from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float
    a: float = 1.0

    def __post_init__(self) -> None:
        for name, value in (("r", self.r), ("g", self.g), ("b", self.b), ("a", self.a)):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} component must be between 0 and 1, got {value!r}")

    @classmethod
    def from_hex(cls, value: str) -> Color:
        text = value.strip()
        if text.startswith("#"):
            text = text[1:]
        if len(text) != 6:
            raise ValueError(f"expected #RRGGBB color, got {value!r}")
        return cls(
            int(text[0:2], 16) / 255.0,
            int(text[2:4], 16) / 255.0,
            int(text[4:6], 16) / 255.0,
        )

    @classmethod
    def from_iterm_dict(cls, value: dict[str, object]) -> Color:
        try:
            return cls(
                float(value.get("Red Component", 0.0)),
                float(value.get("Green Component", 0.0)),
                float(value.get("Blue Component", 0.0)),
                float(value.get("Alpha Component", 1.0)),
            )
        except TypeError as exc:
            raise ValueError(f"invalid color component in iTerm dict: {exc}") from exc

    def to_hex(self) -> str:
        return f"#{round(self.r * 255):02X}{round(self.g * 255):02X}{round(self.b * 255):02X}"

    def to_iterm_dict(self) -> dict[str, object]:
        return {
            "Color Space": "sRGB",
            "Red Component": self.r,
            "Green Component": self.g,
            "Blue Component": self.b,
            "Alpha Component": self.a,
        }

    def relative_luminance(self) -> float:
        def channel(c: float) -> float:
            if c <= 0.03928:
                return c / 12.92
            return ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(self.r) + 0.7152 * channel(self.g) + 0.0722 * channel(self.b)

    def blend_over(self, background: Color) -> Color:
        alpha = self.a
        return Color(
            self.r * alpha + background.r * (1 - alpha),
            self.g * alpha + background.g * (1 - alpha),
            self.b * alpha + background.b * (1 - alpha),
            1.0,
        )
