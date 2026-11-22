"""The actuator seam: one module performs an action on the Mac.

Tests drive the recording adapter, so nothing is sent to the machine and no
module global is stubbed. The adapter records the exact events a command
would emit.
"""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_actuator", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def test_recording_actuator_records_scroll_events() -> None:
    act = controller.RecordingActuator()
    assert act.perform("scroll_down", lines=8) is True
    assert act.perform("scroll_up", lines=30) is True
    assert act.events == [("scroll", "down", 8), ("scroll", "up", 30)]


def test_recording_actuator_records_a_key_chord() -> None:
    act = controller.RecordingActuator()
    assert act.key(controller.KEY_EQUAL, ("command",)) is True
    assert act.events == [("key", controller.KEY_EQUAL, ("command",))]


def test_scroll_phrases_still_map_to_the_actuator_actions() -> None:
    # Same recognition as before ticket 06; only the execution moved.
    assert controller.scroll_command("hey jarvis scroll down a lot") == ("scroll_down", 30)
    assert controller.scroll_command("scroll up a little") == ("scroll_up", 3)
    assert controller.scroll_command("scroll down") == ("scroll_down", 8)
    assert controller.scroll_command("scroll to the end") is None


def test_actuator_rejects_an_action_it_does_not_own() -> None:
    act = controller.RecordingActuator()
    assert act.perform("sent") is False
    assert act.events == []
