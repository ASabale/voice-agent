"""Classify the phrases Handy returned from the fixture files.

The strings are the 2026-11-13 --transcribe-file results. The run JSON is
gitignored. This test does not call Handy, open the microphone, or stop playback.
"""

import importlib.machinery
import importlib.util
import queue
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_handy_phrases", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def test_handy_file_phrases_match_the_controller_without_stopping_playback(monkeypatch) -> None:
    stops: list[str] = []
    resumes = 0
    entered: list[str] = []

    monkeypatch.setattr(controller, "stop_playback", lambda reason: stops.append(reason))
    for name in ("dispatch_transcript", "play_cue", "silence_speech", "handy_start_recording", "write_status"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "resume_tts_clips", resume)

    wake = "Hey Jarvis."
    greeting = "Good morning."
    stop = "Stop."
    hold = "Hold on a second."
    sentence = "The sentence ends with stop."

    assert controller.is_wake_phrase(wake) is True
    assert controller.is_wake_phrase(greeting) is False
    assert controller.idle_command(greeting) is None
    paused = controller.idle_command(stop)
    assert paused is not None
    assert paused["action"] == "paused"
    assert controller._is_playback_barge(controller._command_tokens(stop)) is True
    assert controller._is_playback_barge(controller._command_tokens(hold)) is True
    assert controller._is_playback_barge(controller._command_tokens(sentence)) is False

    class _Model:
        def reset(self) -> None:
            return None

    def apply(kind: str, heard: str, *, held: bool = False) -> controller.MicState:
        mic = controller.MicState()
        mic.state = "IDLE"
        mic.tts_barge_held = held
        mic.enter_dictating = lambda reason, *_a, **_k: entered.append(reason)  # type: ignore[method-assign]
        mic.apply_whisper(kind, heard, _Model(), None, queue.Queue(maxsize=1))
        return mic

    woken = apply("idle_verify", wake)
    assert entered == [f"whisper heard {wake!r}"]
    assert woken.state == "IDLE"

    quiet = apply("idle_verify", greeting)
    idle_stop = apply("idle_verify", stop)
    assert entered == [f"whisper heard {wake!r}"]
    assert quiet.state == "IDLE"
    assert idle_stop.state == "IDLE"
    assert stops == []

    stopped = apply("tts_barge", stop, held=True)
    held_on = apply("tts_barge", hold, held=True)
    assert len(stops) == 2
    assert stop in stops[0]
    assert hold in stops[1]
    assert stopped.tts_barge_held is False
    assert held_on.tts_barge_held is False
    assert resumes == 0

    ignored = apply("tts_barge", sentence, held=True)
    assert len(stops) == 2
    assert resumes == 0
    assert ignored.tts_barge_held is False
