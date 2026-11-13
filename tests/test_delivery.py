"""Handy text follows the focused control, not whichever omp grabbed a port."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_delivery", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")

THIS = {"pid": 13703, "tty": "/dev/ttys002", "started_at": 100, "port": None}
OTHER = {"pid": 21526, "tty": "ttys001", "started_at": 200, "port": None}
TEXT = {"role": "AXTextArea", "tty": "/dev/ttys002"}


def test_focused_omp_tab_without_its_own_port_is_a_paste() -> None:
    dest = controller.choose_delivery(TEXT, [THIS, OTHER], legacy_owner_pid=21526)
    assert dest["mode"] == "paste", dest
    assert dest["pid"] == 13703
    assert dest["focused_text"] is True


def test_focused_omp_tab_uses_its_registered_port() -> None:
    focused = {**THIS, "port": 51234}
    dest = controller.choose_delivery(TEXT, [focused, OTHER], legacy_owner_pid=21526)
    assert dest == {"mode": "bridge", "pid": 13703, "port": 51234, "focused_text": True}


def test_focused_omp_that_owns_the_legacy_port_uses_it() -> None:
    dest = controller.choose_delivery(TEXT, [THIS, OTHER], legacy_owner_pid=13703)
    assert dest["mode"] == "bridge", dest
    assert dest["port"] == 17494
    assert dest["pid"] == 13703


def test_editable_control_outside_the_role_list_is_a_paste() -> None:
    dest = controller.choose_delivery(
        {"role": "AXGroup", "editable": True, "tty": None},
        [THIS, OTHER],
        legacy_owner_pid=21526,
    )
    assert dest["mode"] == "paste", dest
    assert dest["focused_text"] is True
    assert dest["pid"] is None


def test_secure_field_in_any_app_is_a_paste() -> None:
    dest = controller.choose_delivery(
        {"role": "AXSecureTextField", "tty": None},
        [THIS, OTHER],
        legacy_owner_pid=21526,
    )
    assert dest["mode"] == "paste", dest
    assert dest["focused_text"] is True
    assert dest["pid"] is None


def test_other_apps_text_field_is_a_paste() -> None:
    dest = controller.choose_delivery(
        {"role": "AXTextField", "tty": None},
        [THIS, OTHER],
        legacy_owner_pid=21526,
    )
    assert dest["mode"] == "paste"
    assert dest["pid"] is None


def test_non_text_focus_goes_to_the_newest_session() -> None:
    newer = {**OTHER, "port": 6000}
    dest = controller.choose_delivery(None, [THIS, newer], legacy_owner_pid=13703)
    assert dest == {"mode": "bridge", "pid": 21526, "port": 6000, "focused_text": False}


def test_non_text_focus_uses_legacy_port_when_newest_owns_it() -> None:
    dest = controller.choose_delivery(None, [THIS, OTHER], legacy_owner_pid=21526)
    assert dest["mode"] == "bridge"
    assert dest["pid"] == 21526
    assert dest["port"] == 17494


def test_send_it_in_a_text_field_is_enter() -> None:
    plan = controller.focused_paste_plan("Send it.")
    assert plan["action"] == "sent", plan
    assert plan["text"] == ""
    assert plan["phrase"] == "send it"


def test_words_before_send_it_are_typed_then_enter() -> None:
    plan = controller.focused_paste_plan("See you send it")
    assert plan == {"action": "sent", "text": "See you", "phrase": "send it"}
    punctuated = controller.focused_paste_plan("See you, send it.")
    assert punctuated["text"] == "See you"
    assert punctuated["action"] == "sent"


def test_draft_commands_are_not_typed_into_the_text_field() -> None:
    for phrase, action in (
        ("Cancel that.", "cancelled"),
        ("Clear draft.", "cleared"),
        ("Clear on.", "cleared"),
        ("Clear all.", "cleared"),
    ):
        plan = controller.focused_paste_plan(phrase)
        assert plan["action"] == action, plan
        assert plan["text"] == ""


def test_plain_dictation_stays_typed() -> None:
    plan = controller.focused_paste_plan("See you tomorrow")
    assert plan["action"] == "appended"
    assert plan["text"] == "See you tomorrow"


def test_status_targets_one_session_port_and_no_legacy() -> None:
    targets = controller.bridge_status_targets([{"port": 56876}], None)
    assert targets == ["http://127.0.0.1:56876"]
    assert "http://127.0.0.1:17494" not in targets


def test_status_targets_empty_when_nothing_is_listening() -> None:
    assert controller.bridge_status_targets([], None) == []


def test_status_targets_legacy_when_session_has_no_port() -> None:
    assert controller.bridge_status_targets([{"pid": 5}], 5) == ["http://127.0.0.1:17494"]


def test_status_targets_session_ports_then_legacy() -> None:
    sessions = [{"port": 1111}, {"port": 2222}]
    assert controller.bridge_status_targets(sessions, 9) == [
        "http://127.0.0.1:1111",
        "http://127.0.0.1:2222",
        "http://127.0.0.1:17494",
    ]


def test_status_targets_legacy_port_on_a_session_is_not_repeated() -> None:
    assert controller.bridge_status_targets([{"port": 17494}], 9) == ["http://127.0.0.1:17494"]


def test_probe_reports_the_session_bridge_and_skips_the_legacy_port(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []

    def fake_request(
        path: str,
        method: str = "GET",
        body: dict | None = None,
        timeout: float = 1,
        base: str | None = None,
    ) -> dict | None:
        del path, method, body, timeout
        seen.append(base)
        if base == "http://127.0.0.1:56876":
            return {"ok": True, "pid": 80894, "speaking": False}
        return None

    monkeypatch.setattr(controller, "bridge_request", fake_request)
    report = controller.probe_bridge_status(
        {"mode": "bridge", "port": 56876},
        ["http://127.0.0.1:56876"],
    )
    assert seen == ["http://127.0.0.1:56876"]
    assert report["ok"] is True
    assert report["url"] == "http://127.0.0.1:56876"
    assert report["pid"] == 80894


def test_probe_asks_the_delivery_port_before_other_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str | None] = []

    def fake_request(
        path: str,
        method: str = "GET",
        body: dict | None = None,
        timeout: float = 1,
        base: str | None = None,
    ) -> dict | None:
        del path, method, body, timeout
        seen.append(base)
        if base == "http://127.0.0.1:56876":
            return {"ok": True}
        return None

    monkeypatch.setattr(controller, "bridge_request", fake_request)
    report = controller.probe_bridge_status(
        {"mode": "bridge", "port": 56876},
        ["http://127.0.0.1:1111", "http://127.0.0.1:56876"],
    )
    assert seen == ["http://127.0.0.1:56876"]
    assert report["url"] == "http://127.0.0.1:56876"


def test_probe_down_omits_the_legacy_port_when_it_is_not_a_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(controller, "bridge_request", lambda *args, **kwargs: None)
    report = controller.probe_bridge_status({"mode": "paste", "port": None}, [])
    assert report == {"ok": False, "note": "No session bridge responded", "targets": []}


def test_probe_down_names_the_legacy_bind_when_17494_was_probed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(controller, "bridge_request", lambda *args, **kwargs: None)
    report = controller.probe_bridge_status(
        {"mode": "bridge", "port": 17494},
        ["http://127.0.0.1:17494"],
    )
    assert report["ok"] is False
    assert report["targets"] == ["http://127.0.0.1:17494"]
    assert "17494" in report["note"]


def test_list_role_is_not_text() -> None:
    dest = controller.choose_delivery(
        {"role": "AXList", "tty": None},
        [OTHER],
        legacy_owner_pid=21526,
    )
    assert dest["mode"] == "bridge"
    assert dest["pid"] == 21526


if __name__ == "__main__":
    test_focused_omp_tab_without_its_own_port_is_a_paste()
    test_focused_omp_tab_uses_its_registered_port()
    test_focused_omp_that_owns_the_legacy_port_uses_it()
    test_editable_control_outside_the_role_list_is_a_paste()
    test_secure_field_in_any_app_is_a_paste()
    test_other_apps_text_field_is_a_paste()
    test_non_text_focus_goes_to_the_newest_session()
    test_non_text_focus_uses_legacy_port_when_newest_owns_it()
    test_send_it_in_a_text_field_is_enter()
    test_words_before_send_it_are_typed_then_enter()
    test_plain_dictation_stays_typed()
    test_list_role_is_not_text()
    print("ok")
