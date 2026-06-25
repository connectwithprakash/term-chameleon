import json

from term_chameleon.cli import main
from term_chameleon.images import Region
from term_chameleon.install import install_profile
from term_chameleon.iterm_connection import ItermConnectionProbe
from term_chameleon.iterm_window import WindowBoundsResult
from term_chameleon.status import collect_status, status_to_json


def test_collect_status_reports_missing_profile(tmp_path):
    report = collect_status(profile_path=tmp_path / "missing.json", live=False)
    by_name = {check.name: check for check in report.checks}
    assert by_name["profile"].ok is False
    assert by_name["iterm-api-connect"].ok is False
    assert "install" in report.recommended_next_command
    assert report.ready_for_live is False


def test_collect_status_reports_installed_profile(tmp_path):
    target, _content = install_profile(target_dir=tmp_path, name="Status Profile", dry_run=False)
    report = collect_status(profile_path=target, live=False)
    by_name = {check.name: check for check in report.checks}
    assert report.profile_installed is True
    assert report.profile_name == "Status Profile"
    assert by_name["profile"].ok is True
    assert by_name["screencapture"].name == "screencapture"
    assert report.recommended_next_command


def test_status_json_is_valid(tmp_path):
    target, _content = install_profile(target_dir=tmp_path, name="Status JSON", dry_run=False)
    report = collect_status(profile_path=target, live=False)
    payload = json.loads(status_to_json(report))
    assert payload["profile_name"] == "Status JSON"
    assert payload["ready_for_live"] is False
    assert {check["name"] for check in payload["checks"]} >= {
        "profile",
        "screencapture",
        "iterm-app",
        "iterm-python-package",
        "iterm-api-connect",
        "iterm-window-bounds",
    }


def test_status_cli_human_output(tmp_path, capsys):
    target, _content = install_profile(target_dir=tmp_path, name="CLI Status", dry_run=False)
    assert main(["status", "--profile", str(target)]) == 0
    out = capsys.readouterr().out
    assert "Term Chameleon version:" in out
    assert "Profile name: CLI Status" in out
    assert "Recommended next command:" in out


def test_status_cli_json_output(tmp_path, capsys):
    target, _content = install_profile(target_dir=tmp_path, name="CLI JSON", dry_run=False)
    assert main(["status", "--profile", str(target), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile_name"] == "CLI JSON"
    assert "recommended_next_command" in payload


def test_status_live_success_with_mocked_probes(monkeypatch, tmp_path):
    import term_chameleon.status as status_module

    target, _content = install_profile(target_dir=tmp_path, name="Live OK", dry_run=False)
    monkeypatch.setattr(
        status_module,
        "probe_iterm_connection",
        lambda: ItermConnectionProbe(True, "connected"),
    )
    monkeypatch.setattr(
        status_module,
        "get_iterm_window_bounds",
        lambda: WindowBoundsResult(True, Region(1, 2, 3, 4), "OK"),
    )
    report = collect_status(profile_path=target, live=True)
    by_name = {check.name: check for check in report.checks}
    assert by_name["iterm-api-connect"].ok is True
    assert by_name["iterm-window-bounds"].ok is True
    assert by_name["iterm-window-bounds"].detail == "1,2,3,4"


def test_status_live_window_bounds_failure_is_not_ready(monkeypatch, tmp_path):
    import term_chameleon.status as status_module

    target, _content = install_profile(target_dir=tmp_path, name="Live Bounds Fail", dry_run=False)
    monkeypatch.setattr(
        status_module,
        "probe_iterm_connection",
        lambda: ItermConnectionProbe(True, "connected"),
    )
    monkeypatch.setattr(
        status_module,
        "get_iterm_window_bounds",
        lambda: WindowBoundsResult(False, None, "iTerm2 has no windows"),
    )
    report = collect_status(profile_path=target, live=True)
    by_name = {check.name: check for check in report.checks}
    assert by_name["iterm-window-bounds"].ok is False
    assert report.ready_for_live is False


def test_status_cli_live_failure_returns_one(monkeypatch, tmp_path, capsys):
    import term_chameleon.status as status_module

    target, _content = install_profile(target_dir=tmp_path, name="CLI Live Fail", dry_run=False)
    monkeypatch.setattr(
        status_module,
        "probe_iterm_connection",
        lambda: ItermConnectionProbe(True, "connected"),
    )
    monkeypatch.setattr(
        status_module,
        "get_iterm_window_bounds",
        lambda: WindowBoundsResult(False, None, "iTerm2 has no windows"),
    )
    assert main(["status", "--profile", str(target), "--live"]) == 1
    out = capsys.readouterr().out
    assert "[warn] iterm-window-bounds: iTerm2 has no windows" in out
