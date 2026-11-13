"""A full microphone queue drops the oldest block and the loss is counted."""

import importlib.machinery
import importlib.util
import json
import queue
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_capture", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


class _Overflow:
    input_overflow = True
    input_underflow = False


def test_full_queue_drops_the_oldest_block() -> None:
    frames: queue.Queue = queue.Queue(maxsize=1)
    assert controller.offer_mic_frame(frames, "old", None) == (0, 0)
    assert controller.offer_mic_frame(frames, "new", None) == (1, 0)
    assert frames.get_nowait() == "new"
    assert frames.empty()


def test_overflow_is_invalid_even_when_the_block_is_queued() -> None:
    frames: queue.Queue = queue.Queue(maxsize=1)
    assert controller.offer_mic_frame(frames, "block", _Overflow()) == (0, 1)


def test_capture_time_stays_on_the_queued_block() -> None:
    frames: queue.Queue = queue.Queue(maxsize=1)
    stamped = controller.stamp_mic_block("pcm", 1000.125)
    assert controller.offer_mic_frame(frames, stamped, None) == (0, 0)
    item = frames.get_nowait()
    assert controller.mic_block_samples(item) == "pcm"
    assert controller.mic_block_captured_at(item) == 1000.125
    assert controller.mic_block_captured_at("pcm") is None


def test_a_late_callback_stamps_the_block_end() -> None:
    frames = 1280
    rate = 16000
    adc = 10.0
    block_end = adc + frames / rate
    wall = 5000.25
    stream_now = block_end + 0.25
    assert controller.block_end_wall_time(wall, adc, stream_now, frames, rate) == 5000.0
    assert controller.block_end_wall_time(wall, adc, block_end, frames, rate) == wall
    assert controller.block_end_wall_time(wall, None, stream_now, frames, rate) == wall
    assert controller.block_end_wall_time(wall, True, stream_now, frames, rate) == wall


def test_a_status_string_is_invalid() -> None:
    frames: queue.Queue = queue.Queue(maxsize=1)
    assert controller.offer_mic_frame(frames, "block", "input overflow") == (0, 1)
    assert controller.frame_status_invalid(None) is False
    assert controller.frame_status_invalid("") is False


def test_status_file_shows_drops_without_erasing_the_last_action(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller, "STATUS_FILE", tmp_path / "status.json")
    (tmp_path / "status.json").write_text(
        json.dumps({"state": "IDLE", "last_action": "sent"}),
        encoding="utf-8",
    )
    controller.record_mic_offer(2, 1)
    controller.publish_capture_totals()
    data = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert data["last_action"] == "sent"
    assert data["mic_dropped"] == 2
    assert data["mic_invalid"] == 1
    text = (tmp_path / "status.json").read_text(encoding="utf-8")
    assert "old" not in text
    assert "block" not in text
