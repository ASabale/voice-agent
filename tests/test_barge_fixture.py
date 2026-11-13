"""A short stop is paused, then Whisper hears it, before playback is allowed to resume.

The thresholds are unchanged. The stop fixture's third hot frame is the last
loud frame, so the old path resumed before recognition.
"""

import importlib.machinery
import importlib.util
import queue
import sys
import wave
from pathlib import Path

import numpy as np
from openwakeword.vad import VAD

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_barge_fixture", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

_FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _wav(name: str) -> np.ndarray:
    with wave.open(str(_FIXTURES / name)) as handle:
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).copy()


def _feed(mic: controller.MicState, pcm: np.ndarray, jobs: queue.Queue, vad: VAD) -> None:
    pad = (-len(pcm)) % 1280
    if pad:
        pcm = np.concatenate([pcm, np.zeros(pad, dtype=np.int16)])
    pcm = np.concatenate([pcm, np.zeros(1280 * 6, dtype=np.int16)])

    class _Oww:
        def reset(self) -> None:
            return None

        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {"hey_jarvis": 0.0}

    for start in range(0, len(pcm), 1280):
        controller.handle_captured_frame(
            mic,
            pcm[start : start + 1280],
            controller.time.time(),
            "fixture",
            _Oww(),
            vad,
            0.40,
            "hey_jarvis",
            0.5,
            5.0,
            15.0,
            jobs,
        )


def test_stop_fixture_is_whispered_before_playback_can_resume(monkeypatch) -> None:
    pauses: list[str] = []
    resumes = 0
    stops: list[str] = []

    monkeypatch.setattr(controller, "pause_tts_clips", lambda: pauses.append("pause"))
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: resumes.__iadd__(1) or None)
    monkeypatch.setattr(controller, "stop_playback", lambda reason: stops.append(reason))
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    for name in ("silence_speech", "kill_tts_clips", "handy_start_recording", "dispatch_transcript", "play_cue", "write_status"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "resume_tts_clips", resume)
    vad = VAD()
    jobs: queue.Queue = queue.Queue(maxsize=1)
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    _feed(mic, _wav("stop-say.wav"), jobs, vad)
    assert pauses == []
    assert resumes == 0
    assert stops == []
    assert mic.tts_barge_waiting is True
    assert mic.whisper_pending is not None
    job = jobs.get_nowait()
    assert job["prompt"] == "Hey Jarvis. stop."
    peak = float(np.max(np.abs(job["audio"])))
    assert peak > 0.2
    mic.apply_whisper("tts_barge", "Stop.", None, vad, jobs)
    assert len(stops) == 1
    assert "Stop." in stops[0]
    assert resumes == 0
    assert mic.state == "IDLE"

    quiet = controller.MicState()
    quiet.last_manual_check = 1e12
    quiet.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    before = len(pauses)
    _feed(quiet, np.zeros(1280 * 10, dtype=np.int16), queue.Queue(maxsize=1), VAD())
    assert len(pauses) == before
    assert quiet.tts_barge_held is False
