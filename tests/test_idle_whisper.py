"""A busy Whisper keeps one idle clip and one interruption clip."""

import importlib.machinery
import importlib.util
import queue
import sys
from pathlib import Path

import numpy as np

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_idle", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def test_a_busy_whisper_keeps_the_newest_idle_clip() -> None:
    mic = controller.MicState()
    jobs: queue.Queue = queue.Queue(maxsize=1)
    first = np.ones(8, dtype=np.float32)
    newer = np.full(8, 2, dtype=np.float32)
    assert mic.kick_whisper(jobs, "partial", first, "busy") is True
    assert mic.hold_idle_utterance(newer, "one") == "held"
    assert mic.hold_idle_utterance(newer, "two") == "replaced"
    assert mic.release_idle_utterance(jobs) is False
    busy = jobs.get_nowait()
    busy["slot"].put("partial text")
    assert mic.take_whisper() == ("partial", "partial text")
    assert mic.release_idle_utterance(jobs) is True
    job = jobs.get_nowait()
    assert job["prompt"] == "two"
    assert np.array_equal(job["audio"], newer)
    assert mic.idle_verify_next is None


def test_a_full_whisper_queue_holds_the_newest_barge_clip() -> None:
    mic = controller.MicState()
    jobs: queue.Queue = queue.Queue(maxsize=1)
    jobs.put_nowait({"audio": np.ones(4, dtype=np.float32), "prompt": "busy", "slot": queue.Queue(maxsize=1)})
    barge = np.full(4, 3, dtype=np.float32)
    assert mic.kick_whisper(jobs, "tts_barge", barge, "one") is False
    assert mic.kick_whisper(jobs, "tts_barge", barge, "two") is False
    assert mic.tts_barge_next is not None
    assert mic.tts_barge_next[1] == "two"
    assert mic.release_barge_clip(jobs) is False
    jobs.get_nowait()
    assert mic.release_barge_clip(jobs) is True
    job = jobs.get_nowait()
    assert job["prompt"] == "two"
    assert np.array_equal(job["audio"], barge)
    assert mic.tts_barge_next is None


def test_dictation_drops_a_held_idle_clip() -> None:
    mic = controller.MicState()
    jobs: queue.Queue = queue.Queue(maxsize=1)
    mic.hold_idle_utterance(np.ones(4, dtype=np.float32), "later")
    mic.state = "DICTATING"
    assert mic.release_idle_utterance(jobs) is False
    assert mic.idle_verify_next is None
    assert jobs.empty()
