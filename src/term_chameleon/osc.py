from __future__ import annotations

from dataclasses import dataclass

from .presets import COLOR_FIELD_MAP, get_preset

ESC = "\x1b"
ST = ESC + "\\"

ANSI_INDEX_BY_ATTR = {
    "ansi_black": 0,
    "ansi_white": 7,
    "ansi_bright_black": 8,
    "ansi_bright_white": 15,
}


@dataclass(frozen=True)
class OscSequence:
    description: str
    sequence: str

    def escaped(self) -> str:
        return self.sequence.encode("unicode_escape").decode("ascii")


def osc(code: str, payload: str, *, terminator: str = ST) -> str:
    return f"{ESC}]{code};{payload}{terminator}"


def query_dynamic_color(code: int) -> str:
    return osc(str(code), "?", terminator=ST)


def reset_sequences() -> list[OscSequence]:
    return [
        OscSequence("reset palette colors", f"{ESC}]104{ST}"),
        OscSequence("reset foreground", f"{ESC}]110{ST}"),
        OscSequence("reset background", f"{ESC}]111{ST}"),
        OscSequence("reset cursor", f"{ESC}]112{ST}"),
    ]


def sequences_for_preset(preset_name: str, *, terminator: str = ST) -> list[OscSequence]:
    preset = get_preset(preset_name)
    seqs = [
        OscSequence(
            "set default foreground", osc("10", preset.foreground.to_hex(), terminator=terminator)
        ),
        OscSequence(
            "set default background", osc("11", preset.background.to_hex(), terminator=terminator)
        ),
        OscSequence("set cursor", osc("12", preset.cursor.to_hex(), terminator=terminator)),
    ]
    for attr, index in ANSI_INDEX_BY_ATTR.items():
        color = getattr(preset, attr)
        seqs.append(
            OscSequence(
                f"set ANSI palette index {index}",
                osc("4", f"{index};{color.to_hex()}", terminator=terminator),
            )
        )
    return seqs


def tmux_wrap(sequence: str) -> str:
    """Wrap an OSC sequence for tmux DCS passthrough."""
    escaped_payload = sequence.replace(ESC, ESC + ESC)
    return f"{ESC}Ptmux;{escaped_payload}{ST}"


def shell_printf(sequences: list[OscSequence], *, tmux: bool = False) -> str:
    payload = "".join(tmux_wrap(s.sequence) if tmux else s.sequence for s in sequences)
    escaped = payload.encode("unicode_escape").decode("ascii")
    return f"printf '{escaped}'"


def supported_color_fields() -> list[str]:
    return sorted(COLOR_FIELD_MAP)
