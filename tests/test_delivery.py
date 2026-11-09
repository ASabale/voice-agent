"""Handy text follows the focused control, not whichever omp grabbed a port."""

import importlib.machinery
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
controller = importlib.machinery.SourceFileLoader(
    "omp_voice_controller_delivery", str(_PATH)
).load_module()

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
    test_other_apps_text_field_is_a_paste()
    test_non_text_focus_goes_to_the_newest_session()
    test_non_text_focus_uses_legacy_port_when_newest_owns_it()
    test_list_role_is_not_text()
    print("ok")
