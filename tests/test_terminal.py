import os
from unittest.mock import patch

from term_chameleon.terminal import apply_osc_to_terminal, detect_terminal


def test_detect_iterm2():
    with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app"}):
        info = detect_terminal()
    assert info.is_iterm2 is True
    assert info.name == "iterm2"
    assert info.supports_osc is True
    assert info.supports_live_session is True


def test_detect_kitty():
    with patch.dict(os.environ, {"TERM_PROGRAM": "kitty"}):
        info = detect_terminal()
    assert info.is_kitty is True
    assert info.name == "kitty"
    assert info.supports_osc is True
    assert info.supports_live_session is False


def test_detect_ghostty():
    with patch.dict(
        os.environ, {"GHOSTTY_RESOURCES_DIR": "/Applications/Ghostty.app/Contents/Resources"}
    ):
        info = detect_terminal()
    assert info.is_ghostty is True
    assert info.name == "ghostty"
    assert info.supports_osc is True
    assert info.supports_live_session is False


def test_detect_alacritty():
    with patch.dict(os.environ, {"TERM_PROGRAM": "Alacritty"}):
        info = detect_terminal()
    assert info.is_alacritty is True
    assert info.name == "alacritty"
    assert info.supports_osc is True


def test_detect_unknown_terminal():
    with patch.dict(os.environ, {"TERM_PROGRAM": ""}, clear=True):
        info = detect_terminal()
    assert info.is_supported is False
    assert info.name == "unknown"


def test_apply_osc_to_terminal_writes_sequences(capsys):
    apply_osc_to_terminal("balanced")
    captured = capsys.readouterr()
    assert "\x1b]10;" in captured.out
    assert "\x1b]11;" in captured.out


def test_apply_osc_to_terminal_reset(capsys):
    apply_osc_to_terminal("balanced", reset=True)
    captured = capsys.readouterr()
    assert "\x1b]104" in captured.out


def test_apply_osc_to_terminal_write_error():
    """Test that OSError from stdout.write is properly raised."""
    import pytest

    with patch("sys.stdout") as mock_stdout:
        mock_stdout.write.side_effect = OSError("pipe error")
        with patch("term_chameleon.osc.sequences_for_preset") as mock_seqs:
            mock_seqs.return_value = []
            with pytest.raises(OSError) as exc_info:
                apply_osc_to_terminal("balanced")
    assert "Failed to write OSC sequences to terminal" in str(exc_info.value)
    assert "pipe error" in str(exc_info.value)


def test_apply_osc_to_terminal_flush_error():
    """Test that OSError from stdout.flush is properly raised."""
    import pytest

    with patch("sys.stdout") as mock_stdout:
        mock_stdout.flush.side_effect = OSError("flush error")
        with patch("term_chameleon.osc.sequences_for_preset") as mock_seqs:
            mock_seqs.return_value = []
            with pytest.raises(OSError) as exc_info:
                apply_osc_to_terminal("balanced")
    assert "Failed to write OSC sequences to terminal" in str(exc_info.value)
    assert "flush error" in str(exc_info.value)
