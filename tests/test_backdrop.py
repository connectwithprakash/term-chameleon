"""Tier-1: backdrop-capture backend selection. The watcher uses ScreenCaptureKit
(true backdrop, excludes the terminal) when the optional 'sck' extra is importable,
and falls back transparently to the screencapture composite grab otherwise. SCK is
never a hard dependency."""

from __future__ import annotations

import json

from term_chameleon import backdrop
from term_chameleon.cli import main


def test_capability_falls_back_when_sck_absent(monkeypatch):
    monkeypatch.setattr(backdrop, "_sck_importable", lambda: False)
    cap = backdrop.detect_backdrop_capability()
    assert cap.backend == "screencapture"
    assert cap.sck_importable is False
    assert "ScreenCaptureKit" in cap.reason


def test_capability_selects_sck_when_present(monkeypatch):
    monkeypatch.setattr(backdrop, "_sck_importable", lambda: True)
    cap = backdrop.detect_backdrop_capability()
    assert cap.backend == "screencapturekit"
    assert cap.sck_importable is True


def test_sck_is_not_a_hard_dependency():
    # detect must work with no SCK installed (the real test environment).
    cap = backdrop.detect_backdrop_capability()
    assert cap.backend in {"screencapture", "screencapturekit"}


def test_backdrop_info_command_human(capsys):
    assert main(["backdrop-info"]) == 0
    out = capsys.readouterr().out
    assert "Backdrop backend:" in out


def test_backdrop_info_command_json(capsys):
    assert main(["backdrop-info", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"] in {"screencapture", "screencapturekit"}
    assert "sck_importable" in payload
