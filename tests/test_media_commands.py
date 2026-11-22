"""Browser and media commands: phrase -> action -> events the actuator sends.

Expected events are written from the ticket's key table, not recomputed from
the code. The recording adapter is the seam, so nothing reaches the machine.
"""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_media", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

_GRAMMAR = controller.load_command_grammar(_ROOT / "grammar.json")

# Expected events come from ticket 07's key table, not from the code.
# ("key", keycode, modifiers) / ("scroll", direction, lines).
_COMMAND_TABLE = [
    ("scroll to the end", "scroll_end", [("key", controller.KEY_END, ())]),
    ("scroll to the bottom", "scroll_end", [("key", controller.KEY_END, ())]),
    ("scroll to the top", "scroll_top", [("key", controller.KEY_HOME, ())]),
    ("page down", "page_down", [("key", controller.KEY_PAGE_DOWN, ())]),
    ("page up", "page_up", [("key", controller.KEY_PAGE_UP, ())]),
    ("full screen", "full_screen", [("key", controller.KEY_F, ("control", "command"))]),
    ("exit full screen", "exit_full_screen", [("key", controller.KEY_F, ("control", "command"))]),
    ("play video", "play_video", [("key", controller.KEY_SPACE, ())]),
    ("pause video", "pause_video", [("key", controller.KEY_SPACE, ())]),
    ("resume video", "play_video", [("key", controller.KEY_SPACE, ())]),
    ("go back", "go_back", [("key", controller.KEY_LEFT_BRACKET, ("command",))]),
    ("go forward", "go_forward", [("key", controller.KEY_RIGHT_BRACKET, ("command",))]),
    ("next tab", "next_tab", [("key", controller.KEY_TAB, ("control",))]),
    ("previous tab", "previous_tab", [("key", controller.KEY_TAB, ("control", "shift"))]),
    ("new tab", "new_tab", [("key", controller.KEY_T, ("command",))]),
    ("close tab", "close_tab", [("key", controller.KEY_W, ("command",))]),
    ("zoom in", "zoom_in", [("key", controller.KEY_EQUAL, ("command",))]),
    ("zoom out", "zoom_out", [("key", controller.KEY_MINUS, ("command",))]),
]

# On YouTube the site's own shortcuts beat the generic keys.
_YOUTUBE_TABLE = [
    ("full screen", [("key", controller.KEY_F, ())]),
    ("exit full screen", [("key", controller.KEY_ESCAPE, ())]),
    ("play video", [("key", controller.KEY_K, ())]),
    ("pause video", [("key", controller.KEY_K, ())]),
]


def _front(name: str, url: str | None) -> controller.FrontApp:
    return controller.FrontApp(name, url)


def test_video_words_do_not_steal_the_dictation_pause() -> None:
    assert controller.match_command("pause", grammar=_GRAMMAR)["action"] == "paused"
    assert controller.match_command("stop", grammar=_GRAMMAR)["action"] == "paused"
    assert controller.match_command("hey jarvis pause", grammar=_GRAMMAR)["action"] == "paused"
    assert controller.match_command("pause video", grammar=_GRAMMAR)["action"] == "pause_video"
    assert controller.match_command("hey jarvis stop the video", grammar=_GRAMMAR)["action"] == "pause_video"


@pytest.mark.parametrize("phrase, action, events", _COMMAND_TABLE)
def test_every_command_phrase_sends_the_table_events(phrase: str, action: str, events: list[tuple]) -> None:
    for heard in (phrase, f"hey jarvis {phrase}", f"can you {phrase}"):
        matched = controller.match_command(heard, grammar=_GRAMMAR)
        assert matched is not None, heard
        assert matched["action"] == action, heard
        act = controller.RecordingActuator(_front("Chrome", "https://example.com/watch"))
        assert act.perform(action) is True
        assert act.events == events, heard


@pytest.mark.parametrize("phrase, events", _YOUTUBE_TABLE)
def test_youtube_pages_use_the_site_shortcuts(phrase: str, events: list[tuple]) -> None:
    matched = controller.match_command(f"hey jarvis {phrase}", grammar=_GRAMMAR)
    assert matched is not None
    act = controller.RecordingActuator(_front("Google Chrome", "https://www.youtube.com/watch?v=abc"))
    assert act.perform(matched["action"]) is True
    assert act.events == events


def test_a_command_never_reaches_the_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    act = controller.RecordingActuator(_front("Google Chrome", "https://www.youtube.com/watch?v=abc"))
    monkeypatch.setattr(controller, "ACTUATOR", act)

    def unreachable(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("an actuator command must not touch delivery")

    monkeypatch.setattr(controller, "resolve_delivery", unreachable)

    result = controller.dispatch_transcript("hey jarvis zoom in")
    assert result["action"] == "command"
    assert result["command"] == "zoom_in"
    assert act.events == [("key", controller.KEY_EQUAL, ("command",))]


def test_a_phrase_that_matches_nothing_is_kept_for_the_intent_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = controller.STATE_DIR / "unmatched.jsonl"

    mic = controller.MicState()
    mic.state = "IDLE"
    assert mic.apply_whisper("idle_verify", "hey jarvis flip the widget", None, None) is False

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["text"] == "hey jarvis flip the widget"
    assert rows[0]["reason"] == "idle_no_match"


def test_only_fast_tails_without_a_command_are_kept() -> None:
    path = controller.STATE_DIR / "unmatched.jsonl"

    mic = controller.MicState()
    mic.state = "DICTATING"
    assert mic.apply_whisper("fast_cmd", "zoom in", None, None) is False
    assert mic.pending_fast_flush is True
    assert mic.apply_whisper("fast_cmd", "hey jarvis flip the widget", None, None) is False

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [row["reason"] for row in rows] == ["fast_tail_no_match"]


def test_a_fired_command_chimes_once_through_the_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    act = controller.RecordingActuator()
    monkeypatch.setattr(controller, "ACTUATOR", act)

    assert controller.dispatch_transcript("hey jarvis zoom in")["action"] == "command"
    assert act.sounds == [(controller.AFPLAY, controller.COMMAND_SOUND)]
    assert not any("omp-vb-" in token for sound in act.sounds for token in sound)


def test_a_scrolled_command_chimes_too(monkeypatch: pytest.MonkeyPatch) -> None:
    act = controller.RecordingActuator()
    monkeypatch.setattr(controller, "ACTUATOR", act)

    assert controller.dispatch_transcript("scroll down a lot")["action"] == "scrolled"
    assert act.events == [("scroll", "down", 30)]
    assert act.sounds == [(controller.AFPLAY, controller.COMMAND_SOUND)]


def test_an_empty_command_sound_is_not_played(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(controller, "COMMAND_SOUND", "")
    act = controller.RecordingActuator()

    assert act.perform("zoom_in") is True
    assert act.sounds == []

