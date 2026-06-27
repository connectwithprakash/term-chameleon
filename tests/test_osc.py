from term_chameleon.osc import (
    OscSequence,
    osc,
    reset_sequences,
    sequences_for_preset,
    shell_printf,
    tmux_wrap,
)
from term_chameleon.presets import get_preset

ESC = "\x1b"
ST = ESC + "\\"


def test_osc_builds_correct_sequence():
    assert osc("10", "#ffffff") == f"{ESC}]10;#ffffff{ST}"


def test_osc_with_custom_terminator():
    assert osc("10", "#fff", terminator="\x07") == f"{ESC}]10;#fff\x07"


def test_reset_sequences_covers_core_resets():
    seqs = reset_sequences()
    descriptions = [s.description for s in seqs]
    assert len(seqs) == 4
    assert "reset palette colors" in descriptions
    assert "reset foreground" in descriptions
    assert "reset background" in descriptions
    assert "reset cursor" in descriptions


def test_sequences_for_preset_balanced():
    preset = get_preset("balanced")
    seqs = sequences_for_preset("balanced")
    assert len(seqs) >= 3 + 4  # fg, bg, cursor + 4 ANSI
    descriptions = [s.description for s in seqs]
    assert "set default foreground" in descriptions
    assert "set default background" in descriptions
    assert "set cursor" in descriptions
    payloads = [s.sequence for s in seqs]
    assert any(preset.foreground.to_hex() in p for p in payloads)


def test_osc_sequence_escaped():
    seq = OscSequence("test", f"{ESC}]10;#fff{ST}")
    escaped = seq.escaped()
    assert "\\x1b" in escaped
    assert ESC not in escaped


def test_tmux_wrap_escapes_esc():
    raw = f"{ESC}]10;#fff{ST}"
    wrapped = tmux_wrap(raw)
    assert wrapped.startswith(f"{ESC}Ptmux;")
    assert wrapped.endswith(ST)
    assert raw.replace(ESC, ESC + ESC) in wrapped


def test_shell_printf_without_tmux():
    seqs = [OscSequence("test", f"{ESC}]10;#fff{ST}")]
    result = shell_printf(seqs)
    assert result.startswith("printf %b ")
    assert "\\x1b" in result


def test_shell_printf_with_tmux():
    seqs = [OscSequence("test", f"{ESC}]10;#fff{ST}")]
    result = shell_printf(seqs, tmux=True)
    assert result.startswith("printf %b ")
    assert "\\x1bPtmux" in result
