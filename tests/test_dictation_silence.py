"""Two-stage silence: pause_seconds flushes a chunk, END_SILENCE_SECONDS ends the take."""

import importlib.machinery
import importlib.util
import queue
import sys
from pathlib import Path

import numpy as np
import pytest

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_silence", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

FRAME = np.full(controller.MIC_CHUNK, 1000, dtype=np.int16)
STEP = controller.MIC_CHUNK / controller.MIC_RATE


class _Vad:
    def reset_states(self) -> None:
        pass


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setenv("OMP_VOICE_HANDY", "transcribe-file")
    monkeypatch.setattr(controller, "transcribe_handy_file", lambda frames: "hello there")
    monkeypatch.setattr(controller, "dispatch_transcript", lambda text: {"action": "appended", "draft": text})
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    monkeypatch.setattr(controller, "play_cue", lambda *a, **k: None)
    monkeypatch.setattr(controller, "write_status", lambda *a, **k: None)
    monkeypatch.setattr(controller.time, "sleep", lambda s: None)
    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.chunk_started_at = 0.0
    mic.last_speech_at = 0.0
    mic.last_real_speech_at = 0.0
    idles: list[str] = []
    monkeypatch.setattr(
        mic, "transition_to_idle", lambda reason, *a, **k: (idles.append(reason), setattr(mic, "state", "IDLE"))
    )
    jobs: queue.Queue = queue.Queue(maxsize=1)

    def feed(now: float, speech: bool) -> None:
        if mic.state != "DICTATING":
            return
        mic.handle_dictating_frame(
            FRAME, now, 1000.0 if speech else 0.0, 0.9 if speech else 0.0, speech, None, _Vad(), 2.0, 15.0, jobs
        )

    return mic, idles, feed


def _run(feed, start: float, seconds: float, speech: bool) -> float:
    now = start
    while now < start + seconds:
        now += STEP
        feed(now, speech)
    return now


def test_two_second_pause_flushes_chunk_and_keeps_listening(rig) -> None:
    mic, idles, feed = rig
    now = _run(feed, 0.0, 1.0, True)
    now = _run(feed, now, 2.3, False)
    assert mic.flushed_this_turn is True
    assert idles == []


def test_five_seconds_of_total_silence_ends_the_take_after_the_flush(rig) -> None:
    mic, idles, feed = rig
    now = _run(feed, 0.0, 1.0, True)
    _run(feed, now, 5.5, False)
    assert mic.flushed_this_turn is True
    assert idles == ["silence_end"]


def test_speech_inside_the_window_postpones_the_end(rig) -> None:
    mic, idles, feed = rig
    now = _run(feed, 0.0, 1.0, True)
    now = _run(feed, now, 3.0, False)  # flushed at 2 s, still listening at 3 s
    now = _run(feed, now, 1.0, True)  # resumes talking
    _run(feed, now, 3.0, False)
    assert idles == []
