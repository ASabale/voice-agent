"""The flush path must not stall the mic consumer past the queue buffer.

VA-AUD-004: the observed 5 `mic_dropped` frames in the VA-SOAK-006 run-3
came from the frame loop blocking on a synchronous Whisper round-trip while
the callback thread kept offering 12.5 blocks/second into a 32-block queue.
"""

import importlib.machinery
import importlib.util
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_stall", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

BLOCK_MS = controller.MIC_CHUNK / controller.MIC_RATE * 1000.0  # 80 ms per block


class _SlowWorker:
    """Emulates the Whisper worker thread: sleeps `delay` before answering each job."""

    def __init__(self, jobs: queue.Queue, delay: float) -> None:
        self.jobs = jobs
        self.delay = delay
        self._stop = threading.Event()

        def run() -> None:
            while not self._stop.is_set():
                try:
                    job = jobs.get(timeout=0.1)
                except queue.Empty:
                    continue
                time.sleep(self.delay)
                job["slot"].put("transcript")

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self._stop.set()


def _dictating_mic() -> controller.MicState:
    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    mic.dict_speech_frames = [np.full(controller.MIC_CHUNK, 1000, dtype=np.int16) for _ in range(10)]
    return mic


def test_queue_full_drops_one_block_per_offer_at_real_stall_size() -> None:
    """Reproduce the magnitude: a 3 s consumer stall at callback cadence (37 offers)
    into the old 32-block queue drops exactly 5 blocks — the number the soak saw."""
    frames: queue.Queue = queue.Queue(maxsize=32)
    dropped = 0
    for i in range(37):  # 3 s at 12.5 blocks/s
        dropped += controller.offer_mic_frame(frames, f"block-{i}", None)[0]
    assert dropped == 5


def test_local_fallback_returns_empty_immediately_when_whisper_is_busy() -> None:
    jobs: queue.Queue = queue.Queue(maxsize=1)
    worker = _SlowWorker(jobs, 2.0)
    mic = _dictating_mic()
    slot: queue.Queue = queue.Queue(maxsize=1)
    jobs.put_nowait({"audio": np.zeros(4, dtype=np.float32), "prompt": "partial", "slot": slot})
    mic.whisper_pending = {"kind": "partial", "slot": slot}
    started = time.monotonic()
    result = mic.transcribe_local_fallback(jobs, mic.dict_speech_frames)
    elapsed = time.monotonic() - started
    worker.close()
    assert result == ""
    assert elapsed < 0.2, f"local fallback blocked the mic loop for {elapsed:.2f}s while whisper was busy"


def test_local_fallback_transcribes_when_whisper_is_free() -> None:
    jobs: queue.Queue = queue.Queue(maxsize=1)
    worker = _SlowWorker(jobs, 0.2)
    mic = _dictating_mic()
    result = mic.transcribe_local_fallback(jobs, mic.dict_speech_frames)
    worker.close()
    assert result == "transcript"


def test_production_queue_absorbs_a_full_flush_stall_without_loss() -> None:
    """8 s of callback blocks with no consumer must be kept in order, oldest first."""
    source = controller.SoundDeviceAudioSource()  # queue built, microphone never opened
    dropped = 0
    for i in range(100):  # 8 s at 12.5 blocks/s
        dropped += controller.offer_mic_frame(source.frames, f"block-{i}", None)[0]
    assert dropped == 0, f"queue dropped {dropped} blocks during an 8 s stall"
    drained = [controller.mic_block_samples(source.frames.get_nowait()) for _ in range(100)]
    assert drained[0] == "block-0" and drained[-1] == "block-99"
    assert source.frames.maxsize * BLOCK_MS / 1000.0 >= 8.0, "buffer must cover at least 8 s of stall"
