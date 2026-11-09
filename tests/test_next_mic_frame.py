"""A mic-device change must be noticed while no audio is arriving.

stream.abort() returns and stream.read() does not, so a device check that sits
behind a blocking read never runs. next_mic_frame has to give up within about
half a second and report the new device.
"""

import importlib.machinery
import queue
import threading
import time
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
controller = importlib.machinery.SourceFileLoader(
    "omp_voice_controller", str(_PATH)
).load_module()


def _call(frames, active, device_id, last_check, check_every):
    holder: dict = {}

    def run() -> None:
        holder["result"] = controller.next_mic_frame(
            frames, active, device_id, last_check, check_every
        )

    thread = threading.Thread(target=run, daemon=True)
    started = time.monotonic()
    thread.start()
    thread.join(2.0)
    elapsed = time.monotonic() - started
    assert not thread.is_alive(), "next_mic_frame blocked with no audio"
    return holder["result"], elapsed


def test_device_change_returns_without_audio() -> None:
    frames: queue.Queue = queue.Queue()
    result, elapsed = _call(frames, 78, lambda: 979, last_check=0.0, check_every=0.4)
    kind, block, _last = result
    assert kind == "rebind", result
    assert block is None
    assert elapsed < 1.0


def test_waiting_for_audio_is_bounded() -> None:
    frames: queue.Queue = queue.Queue()
    result, elapsed = _call(
        frames, 78, lambda: 78, last_check=time.monotonic(), check_every=2.0
    )
    kind, block, _last = result
    assert kind == "idle", result
    assert block is None
    assert elapsed < 0.8


def test_queued_audio_is_returned_immediately() -> None:
    frames: queue.Queue = queue.Queue()
    frames.put("pcm")
    result, elapsed = _call(
        frames, 78, lambda: 78, last_check=time.monotonic(), check_every=2.0
    )
    kind, block, _last = result
    assert kind == "frame", result
    assert block == "pcm"
    assert elapsed < 0.3


if __name__ == "__main__":
    test_device_change_returns_without_audio()
    test_waiting_for_audio_is_bounded()
    test_queued_audio_is_returned_immediately()
    print("ok")
