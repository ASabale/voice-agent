"""Stop, pause, resume, and hold-on are different commands.

This does not open the microphone and does not stop playback. It is not
evidence that a fixture entered the controller's input stream.
"""

import importlib.machinery
import importlib.util
import queue
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_semantics", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def _barge(text: str) -> bool:
    return controller._is_playback_barge(controller._command_tokens(text))


def test_stop_and_hold_cut_playback_pause_and_resume_do_not(monkeypatch) -> None:
    stops: list[str] = []
    resumes = 0

    def stop(reason: str) -> None:
        stops.append(reason)

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "stop_playback", stop)
    monkeypatch.setattr(controller, "resume_tts_clips", resume)
    for name in ("dispatch_transcript", "play_cue", "silence_speech", "handy_start_recording", "write_status"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    assert _barge("Stop.") is True
    assert _barge("hold on a second") is True
    assert _barge("pause") is False
    assert _barge("the pause command") is False
    assert _barge("resume") is False

    assert controller.match_command("stop")["action"] == "paused"
    assert controller.match_command("pause")["action"] == "paused"
    assert controller.match_command("hold on a second") is None
    assert controller.match_command("resume") is None
    assert controller.is_wake_phrase("hold on a second") is False
    assert controller.is_wake_phrase("resume") is False

    class _Model:
        def reset(self) -> None:
            return None

    def apply(kind: str, heard: str) -> None:
        mic = controller.MicState()
        mic.state = "IDLE"
        mic.tts_barge_held = True
        mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
        mic.apply_whisper(kind, heard, _Model(), None, queue.Queue(maxsize=1))

    apply("tts_barge", "Stop.")
    apply("tts_barge", "Hold on a second.")
    assert len(stops) == 2
    assert resumes == 0

    # A barge that is not a stop does not signal the player: it was never paused.
    apply("tts_barge", "pause")
    apply("tts_barge", "the pause command")
    apply("tts_barge", "resume")
    assert len(stops) == 2
    assert resumes == 0

    # An idle_verify result does not signal the player either.
    apply("idle_verify", "Stop.")
    apply("idle_verify", "pause")
    apply("idle_verify", "resume")
    assert len(stops) == 2
    assert resumes == 0
