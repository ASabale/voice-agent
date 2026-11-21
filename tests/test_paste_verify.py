"""VA-PASTE-002: paste landing verification in fallback_macos_inject (Level 1).

The dispatch path used to report "appended" for a paste that never reached
the target element (VA-PASTE-001). These tests drive the production
`fallback_macos_inject` with a stubbed clipboard, keystroke runner, and
focused-value reader, and assert the verification verdict, its logging,
and the clipboard-restore ordering.
"""
import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_paste", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, loader=_loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def _wire(monkeypatch, focused_value, keystrokes, clipboard):
    """Record subprocess/keystroke calls; `focused_value` drives the read-back."""

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "/usr/bin/pbpaste":
            return subprocess.CompletedProcess(cmd, 0, clipboard[0], "")
        if cmd[0] == "/usr/bin/pbcopy":
            clipboard[0] = kwargs.get("input", b"")
        if cmd[0] == "/usr/bin/osascript":
            keystrokes.append(cmd[2])
            # The value-read script returns the focused element's contents;
            # keystroke scripts return nothing.
            if "AXFocusedUIElement" in cmd[2]:
                return subprocess.CompletedProcess(cmd, 0, focused_value, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    logs: list[str] = []
    monkeypatch.setattr(controller, "log", lambda msg: logs.append(msg))
    return logs


def test_appended_paste_that_lands_returns_true(monkeypatch):
    keystrokes: list[str] = []
    clipboard: list[bytes] = [b"old clipboard"]
    logs = _wire(monkeypatch, "meeting notes 42", keystrokes, clipboard)

    landed = controller.fallback_macos_inject("meeting notes 42 ", "appended")

    assert landed is True
    assert any("Paste verified landed" in line for line in logs)
    # The user's original clipboard is restored, not the injected text.
    assert clipboard == [b"old clipboard"]


def test_missing_paste_is_reported_false_not_silently_appended(monkeypatch):
    keystrokes: list[str] = []
    clipboard: list[bytes] = [b"old clipboard"]
    logs = _wire(monkeypatch, "completely different text", keystrokes, clipboard)

    landed = controller.fallback_macos_inject("meeting notes 42 ", "appended")

    assert landed is False
    assert any("Paste verification FAILED" in line for line in logs)
    assert clipboard == [b"old clipboard"]


def test_unreadable_focus_is_unknown_never_a_confirmed_failure(monkeypatch):
    keystrokes: list[str] = []
    clipboard: list[bytes] = [b"old clipboard"]
    logs = _wire(monkeypatch, None, keystrokes, clipboard)

    landed = controller.fallback_macos_inject("hello ", "appended")

    assert landed is None
    assert not any("FAILED" in line for line in logs)


def test_sent_path_verifies_landing_before_enter_key(monkeypatch):
    keystrokes: list[str] = []
    clipboard: list[bytes] = [b"old clipboard"]
    _wire(monkeypatch, "please send that", keystrokes, clipboard)

    landed = controller.fallback_macos_inject("please send that", "sent")

    assert landed is True
    value_reads = [i for i, s in enumerate(keystrokes) if "AXFocusedUIElement" in s]
    enters = [i for i, s in enumerate(keystrokes) if "key code 36" in s]
    assert len(value_reads) == 1 and len(enters) == 1
    assert value_reads[0] < enters[0]


def test_focus_dispatch_reports_the_verification_verdict(monkeypatch):
    """The dispatch result carries the landing verdict, so `appended` is no
    longer an unqualified success claim."""
    monkeypatch.setattr(
        controller, "focused_paste_plan", lambda _t: {"action": "appended", "text": "ship it", "phrase": ""}
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda _t, _a: False)
    result = controller.paste_into_focus("ship it")
    assert result["verified"] is False

    monkeypatch.setattr(controller, "fallback_macos_inject", lambda _t, _a: True)
    result = controller.paste_into_focus("ship it")
    assert result["verified"] is True


def test_failed_focus_paste_is_logged_as_unverified(monkeypatch):
    monkeypatch.setattr(
        controller, "focused_paste_plan", lambda _t: {"action": "appended", "text": "lost words", "phrase": ""}
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda _t, _a: False)
    logs: list[str] = []
    monkeypatch.setattr(controller, "log", lambda msg: logs.append(msg))

    controller.paste_into_focus("lost words")

    assert any("UNVERIFIED" in line for line in logs)


def test_unknown_verdict_is_neither_claimed_nor_flagged(monkeypatch):
    """An unreadable focus (None) must not produce an UNVERIFIED warning and
    must not be reported as verified."""
    monkeypatch.setattr(
        controller, "focused_paste_plan", lambda _t: {"action": "appended", "text": "hello", "phrase": ""}
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda _t, _a: None)
    logs: list[str] = []
    monkeypatch.setattr(controller, "log", lambda msg: logs.append(msg))

    result = controller.paste_into_focus("hello")

    assert result["verified"] is None
    assert not any("UNVERIFIED" in line for line in logs)


def test_scratch_and_clear_remove_pasted_chunks_only_in_the_same_app(monkeypatch):
    """Live 2026-11-21: "scratch that" in TextEdit reported scratched and left the text."""
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda _t, _a: True)
    erased: list[int] = []
    monkeypatch.setattr(controller, "_backspace", erased.append)
    monkeypatch.setattr(controller, "_pasted_chunks", [])

    controller.paste_into_focus("Add a unit test.", app="TextEdit")
    controller.paste_into_focus("Update the readme.", app="TextEdit")
    assert controller.paste_into_focus("scratch that", app="TextEdit")["action"] == "scratched"
    assert erased == [len("Update the readme. ")]

    controller.paste_into_focus("Also this.", app="TextEdit")
    controller.paste_into_focus("clear draft", app="TextEdit")
    assert erased[-1] == len("Add a unit test. ") + len("Also this. ")

    controller.paste_into_focus("Typed in Chrome.", app="Google Chrome")
    controller.paste_into_focus("scratch that", app="TextEdit")
    assert len(erased) == 2


def test_restore_happens_after_the_landing_read(monkeypatch):
    keystrokes: list[str] = []
    clipboard: list[bytes] = [b"old clipboard"]
    ops: list[str] = []

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "/usr/bin/pbpaste":
            ops.append("save")
            return subprocess.CompletedProcess(cmd, 0, b"old clipboard", "")
        if cmd[0] == "/usr/bin/pbcopy":
            ops.append("restore" if kwargs.get("input") == b"old clipboard" else "inject")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(controller, "_run_osascript", lambda script: None)
    reads: list[int] = []

    def focused_value():
        ops.append("read")
        return "meeting notes 42"

    monkeypatch.setattr(controller, "_focused_element_value", focused_value)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)

    controller.fallback_macos_inject("meeting notes 42 ", "appended")

    # save -> inject -> read-back verification -> restore: the verification
    # runs while the injected clipboard is still in place.
    assert ops == ["save", "inject", "read", "restore"]
