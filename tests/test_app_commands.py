"""App switching by voice: phrase -> resolved app -> events the actuator sends.

The seam is the actuator. The recording adapter is built with an injected app
list, so name resolution is exercised without touching the machine, and the
expected events come from ticket 09, not from the matcher's own logic.
"""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_apps", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

_GRAMMAR = controller.load_command_grammar(_ROOT / "grammar.json")

# An invented inventory. Nothing here is read from the machine.
_APPS = [
    "Google Chrome",
    "Visual Studio Code",
    "Terminal",
    "Finder",
    "System Settings",
    "Slack",
    "Spotify",
]

# phrase -> app the actuator must activate. From ticket 09's table.
_SWITCH_TABLE = [
    ("switch to Chrome", "Google Chrome"),
    ("go to terminal", "Terminal"),
    ("open Slack", "Slack"),
    ("hey jarvis can you switch to Visual Studio Code", "Visual Studio Code"),
    ("switch to chrome", "Google Chrome"),
    ("switch to CHROME", "Google Chrome"),
    ("switch to VS Code", "Visual Studio Code"),
    ("switch to code", "Visual Studio Code"),
    ("switch to settings", "System Settings"),
    ("go to the Terminal", "Terminal"),
    ("switch to Spotify app", "Spotify"),
    ("switch to visual", "Visual Studio Code"),
]

_PREVIOUS_TABLE = ["switch app", "previous app", "last app"]


def _act(front: controller.FrontApp | None = None) -> controller.RecordingActuator:
    return controller.RecordingActuator(front, apps=_APPS)


def test_app_switch_phrases_are_commands_through_the_shared_matcher() -> None:
    for phrase in _PREVIOUS_TABLE:
        for heard in (phrase, f"hey jarvis {phrase}", f"can you {phrase}"):
            matched = controller.match_command(heard, grammar=_GRAMMAR)
            assert matched is not None, heard
            assert matched["action"] == "previous_app", heard
            assert matched["phrase"].endswith(phrase), heard


def test_a_tail_longer_than_a_name_is_not_a_command() -> None:
    assert controller.match_command("go to the store and buy milk", grammar=_GRAMMAR) is None


def test_previous_app_taps_cmd_tab_and_chimes() -> None:
    act = _act()
    assert act.perform("previous_app") is True
    assert act.events == [("key", controller.KEY_TAB, ("command",))]
    assert act.sounds == [(controller.AFPLAY, controller.COMMAND_SOUND)]


def test_a_free_form_app_tail_is_matched_as_a_shape() -> None:
    matched = controller.match_command("hey jarvis can you switch to Visual Studio Code", grammar=_GRAMMAR)
    assert matched is not None
    assert matched["action"] == "switch_to_app"
    assert matched["prefix"] == "hey jarvis can you"
    assert matched["phrase"] == "switch to visual studio code"
    assert matched["tail"] == "visual studio code"


def test_go_to_sleep_is_still_the_pause_command() -> None:
    matched = controller.match_command("go to sleep", grammar=_GRAMMAR)
    assert matched["action"] == "paused"


def test_go_back_is_not_read_as_an_app() -> None:
    matched = controller.match_command("go back", grammar=_GRAMMAR)
    assert matched is not None and matched["action"] == "go_back"
    act = controller.RecordingActuator()
    assert act.perform(matched["action"]) is True
    assert act.events == [("key", controller.KEY_LEFT_BRACKET, ("command",))]
    assert act.sounds == [(controller.AFPLAY, controller.COMMAND_SOUND)]


@pytest.mark.parametrize("tail, expected", [(name, name) for name in _APPS])
def test_exact_app_names_resolve(tail: str, expected: str) -> None:
    assert _act().resolve_app(tail) == expected


@pytest.mark.parametrize("tail, expected", _SWITCH_TABLE)
def test_alias_prefix_and_case_variants_resolve(tail: str, expected: str) -> None:
    phrase = controller.match_command(tail, grammar=_GRAMMAR)
    assert phrase is not None and phrase["action"] == "switch_to_app", tail
    assert _act().resolve_app(phrase["tail"]) == expected, tail


def test_an_unknown_app_resolves_to_nothing() -> None:
    assert _act().resolve_app("the store") is None
    assert _act().resolve_app("NotAnApp") is None


def test_an_alias_beats_a_longer_name_that_merely_starts_with_it() -> None:
    act = controller.RecordingActuator(
        apps=["Chrome Remote Desktop Host Uninstaller", "Google Chrome", "Terminal"]
    )
    assert act.resolve_app("chrome") == "Google Chrome"


def test_activating_resolves_then_records_open_through_the_adapter() -> None:
    act = _act()
    name = act.resolve_app("chrome")
    assert act.perform("switch_to_app", app=name) is True
    assert act.events == [("activate", "Google Chrome")]
    assert act.sounds == [(controller.AFPLAY, controller.COMMAND_SOUND)]


def test_an_unresolvable_app_names_nothing_to_activate() -> None:
    act = _act()
    assert act.perform("switch_to_app", app=act.resolve_app("the store")) is False
    assert act.events == []


@pytest.mark.parametrize("phrase, expected", _SWITCH_TABLE)
def test_dispatch_acts_on_a_named_app(
    phrase: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    act = _act()
    monkeypatch.setattr(controller, "ACTUATOR", act)

    def unreachable(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a switch to an app must not touch delivery")

    monkeypatch.setattr(controller, "resolve_delivery", unreachable)

    for heard in (phrase, f"hey jarvis {phrase}", f"can you {phrase}"):
        result = controller.dispatch_transcript(heard)
        assert result["action"] == "command", heard
        assert result["command"] == "switch_to_app", heard
        assert result["draft"] == "", heard
    assert act.events == [("activate", expected)] * 3
    assert len(act.sounds) == 3


def test_dictation_that_ends_in_go_to_something_unknown_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    act = _act()
    monkeypatch.setattr(controller, "ACTUATOR", act)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "paste", "focused_text": True, "app": "TextEdit", "pid": 1, "port": None},
    )
    monkeypatch.setattr(
        controller,
        "session_bridge_base",
        lambda _dest: None,
    )
    monkeypatch.setattr(
        controller,
        "paste_into_focus",
        lambda text, app=None: {"action": "appended", "draft": text},
    )

    result = controller.dispatch_transcript("I need you to go to the store")
    assert result["action"] == "appended"
    assert result["draft"] == "I need you to go to the store"
    assert act.events == []

    rows = [json.loads(line) for line in (controller.STATE_DIR / "unmatched.jsonl").read_text().splitlines()]
    assert [row["reason"] for row in rows] == ["app_not_found"]
    assert rows[0]["text"] == "I need you to go to the store"


def test_dispatch_acts_on_previous_app(monkeypatch: pytest.MonkeyPatch) -> None:
    act = controller.RecordingActuator()
    monkeypatch.setattr(controller, "ACTUATOR", act)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: (_ for _ in ()).throw(AssertionError("delivery must not be reached")),
    )

    result = controller.dispatch_transcript("hey jarvis switch app")
    assert result["action"] == "command"
    assert result["command"] == "previous_app"
    assert act.events == [("key", controller.KEY_TAB, ("command",))]
