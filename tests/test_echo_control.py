"""WebRTC echo control on the playback reference. Not the microphone."""

import importlib.machinery
import importlib.util
import json
import queue
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_echo", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

# The WebRTC wheel only exists for Apple Silicon / CPython 3.12. Where it is
# absent the controller logs "echo-cancel-missing" and runs the render-subtraction
# fit; that fallback is covered by the tests below that do NOT need the wheel.
# These tests pin WebRTC behaviour specifically and are skipped, not weakened,
# when the library cannot exist on the platform.
_HAS_AEC = importlib.util.find_spec("aec_audio_processing") is not None
aec_required = pytest.mark.skipif(
    not _HAS_AEC,
    reason="WebRTC canceller needs the ARM64 CPython 3.12 wheel; the render-subtraction fallback is tested separately",
)

_FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
_RATE = 16000


def _wav(name: str) -> np.ndarray:
    with wave.open(str(_FIXTURES / name)) as handle:
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).copy()


def _tile(pcm: np.ndarray, seconds: float) -> np.ndarray:
    need = int(seconds * _RATE)
    return np.tile(pcm, int(np.ceil(need / len(pcm))))[:need]


def _rms(samples: np.ndarray) -> float:
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def _erle(mic: np.ndarray, cleaned: np.ndarray) -> float:
    tail = _RATE
    out = _rms(cleaned[-tail:])
    return 20.0 * float(np.log10(_rms(mic[-tail:]) / max(out, 1.0)))


@pytest.fixture(autouse=True)
def _reset_echo_state() -> None:
    controller._echo_ap = None
    controller._echo_key = None
    controller._echo_unavailable = False
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    controller._render_paused_at = None
    controller._render_paused_seconds = 0.0
    yield
    controller._echo_ap = None
    controller._echo_key = None
    controller._echo_unavailable = False
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None


def _stereo_wav(path: Path, left: np.ndarray, right: np.ndarray, rate: int) -> int:
    frames = min(len(left), len(right))
    interleaved = np.empty(frames * 2, dtype=np.int16)
    interleaved[0::2] = left[:frames]
    interleaved[1::2] = right[:frames]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(interleaved.tobytes())
    return frames


def test_downmix_averages_interleaved_channels() -> None:
    interleaved = np.array([100, -100, 200, 600], dtype=np.int16)
    assert np.array_equal(controller.downmix_to_mono(interleaved, 2), np.array([0, 400], dtype=np.int16))
    assert np.array_equal(controller.downmix_to_mono(np.array([7], dtype=np.int16), 1), np.array([7], dtype=np.int16))


def test_a_stereo_clip_downmixes_to_an_aligned_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A 24 kHz stereo VoiceBox-style clip used to stay unaligned and skip AEC entirely.
    speech16 = _tile(_wav("sentence-stop-say.wav"), 4.0)
    speech24 = controller.resample_to_mic_rate(speech16, 16000, 24000)
    left = speech24
    right = (speech24.astype(np.float32) * 0.5).astype(np.int16)
    wav = tmp_path / "stereo-clip.wav"
    frames = _stereo_wav(wav, left, right, 24000)
    slot = {
        "reference": {"wav": str(wav), "sample_rate": 24000, "channels": 2, "frames": frames},
        "started_at": 100.0,
        "playing": True,
        "afplay_pid": 4242,
    }
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [slot])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    fields = controller.refresh_render_reference(100.0)
    assert fields["render_connected"] is True
    assert fields["render_aligned"] is True
    assert fields["render_rate"] == 24000
    interleaved = np.empty(frames * 2, dtype=np.int16)
    interleaved[0::2] = left
    interleaved[1::2] = right
    expected = controller.resample_to_mic_rate(controller.downmix_to_mono(interleaved, 2), 24000)
    assert np.array_equal(controller._render_samples, expected)
    assert len(controller._render_samples) == int(frames * 16000 / 24000)


def test_stereo_playback_echo_is_cancelled_on_the_production_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    speech16 = _tile(_wav("sentence-stop-say.wav"), 4.0)
    speech24 = controller.resample_to_mic_rate(speech16, 16000, 24000)
    left = speech24
    right = (speech24.astype(np.float32) * 0.5).astype(np.int16)
    wav = tmp_path / "stereo-clip.wav"
    frames = _stereo_wav(wav, left, right, 24000)
    slot = {
        "reference": {"wav": str(wav), "sample_rate": 24000, "channels": 2, "frames": frames},
        "started_at": 100.0,
        "playing": True,
        "afplay_pid": 4242,
    }
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [slot])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    controller.refresh_render_reference(100.0)
    reference = controller._render_samples
    assert reference is not None and controller._render_parsed["aligned"]
    # Microphone hears the averaged clip 320 samples late at 60% gain.
    echo = np.zeros(len(reference) + 320, dtype=np.int32)
    echo[320 : 320 + len(reference)] = (0.6 * reference).astype(np.int32)
    mic = np.clip(echo, -32768, 32767).astype(np.int16)
    cleaned: list[np.ndarray] = []
    for i in range(len(mic) // 1280):
        cleaned.append(controller.cancel_playback_echo(mic[i * 1280 : (i + 1) * 1280], 100.0 + (i + 1) * 0.08))
    assert _erle(mic, np.concatenate(cleaned)) >= 12.0


def _grid_slot(tmp_path: Path, seconds: float) -> dict:
    speech16 = _tile(_wav("sentence-stop-say.wav"), seconds)
    speech24 = controller.resample_to_mic_rate(speech16, 16000, 24000)
    right = (speech24.astype(np.float32) * 0.5).astype(np.int16)
    wav = tmp_path / "grid-clip.wav"
    frames = _stereo_wav(wav, speech24, right, 24000)
    return {
        "reference": {"wav": str(wav), "sample_rate": 24000, "channels": 2, "frames": frames},
        "started_at": 100.0,
        "playing": True,
        "afplay_pid": 4242,
        "playback_rate": 1.18,
    }


def test_the_published_cursor_counts_on_the_aec_grid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A 24 kHz clip published a cursor in 24 kHz file samples while both
    # cancellers read the resampled 16 kHz reference. One wall second is now
    # 16000 grid samples, not 24000, and the clamp is the grid length.
    slot = _grid_slot(tmp_path, 4.0)
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [slot])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    fields = controller.refresh_render_reference(100.5)
    assert fields["render_frames"] == 4 * 24000
    assert fields["render_processed_frames"] == 4 * 16000
    assert fields["render_cursor"] == int(0.5 * 16000 * 1.18)
    # Past the end of the clip the cursor clamps to the grid, not the file.
    late = controller.refresh_render_reference(110.0)
    assert late["render_cursor"] == 4 * 16000
    # The published cursor equals the position render_block_at actually reads.
    started = controller.refresh_render_reference(101.0)["render_cursor"]
    block = controller.render_block_at(
        controller._render_samples, 100.0, 101.0, 1280, 1.18, 0.0
    )
    assert np.array_equal(block, controller._render_samples[started - 1280 : started])


def test_the_grid_cursor_freezes_while_afplay_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    slot = _grid_slot(tmp_path, 4.0)
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [slot])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    before = controller.refresh_render_reference(101.0)
    assert before["render_cursor"] == int(1.0 * 16000 * 1.18)
    controller.note_render_paused(101.0)
    stopped = controller.refresh_render_reference(101.5)
    assert stopped["render_cursor"] == int(1.0 * 16000 * 1.18)
    controller.note_render_resumed(101.5)
    resumed = controller.refresh_render_reference(102.0)
    assert resumed["render_cursor"] == int(1.5 * 16000 * 1.18)


def test_echo_block_returns_each_frame_in_order() -> None:
    seen: list[bytes] = []

    class _Processor:
        def process_reverse_stream(self, data: bytes) -> bytes:
            seen.append(data)
            return data

        def process_stream(self, data: bytes) -> bytes:
            return data

    mic = np.arange(1280, dtype=np.int16)
    reverse = np.arange(1000, 2280, dtype=np.int16)
    out = controller.process_echo_block(_Processor(), mic, reverse)
    assert np.array_equal(out, mic)
    assert b"".join(seen) == reverse.tobytes()
    assert len(seen) == 8


def test_render_block_lines_up_with_the_capture_cursor() -> None:
    render = np.arange(5000, dtype=np.int16)
    block = controller.render_block_at(render, 0.0, 2000 / _RATE, 1280, 1.0, 0.0)
    assert np.array_equal(block, render[720:2000])
    early = controller.render_block_at(render, 0.0, 200 / _RATE, 1280, 1.0, 0.0)
    assert np.all(early[:1080] == 0)
    assert np.array_equal(early[1080:], render[:200])


def test_playback_rate_1_18_advances_the_reference() -> None:
    # afplay -r 1.18 consumes 1.18 seconds of the file per wall-clock second.
    # 0.5 s -> int(0.5 * 16000 * 1.18) = 9440. A held 0.25 s does not move the file.
    render = np.arange(12000, dtype=np.int16)
    block = controller.render_block_at(render, 100.0, 100.5, 1280, 1.18, 0.0)
    assert np.array_equal(block, render[8160:9440])
    held = controller.render_block_at(render, 100.0, 100.5, 1280, 1.18, 0.25)
    assert np.array_equal(held, render[3440:4720])


def test_cancel_sends_the_rate_shifted_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[np.ndarray] = []

    def _process(_processor: object, mic: np.ndarray, reverse: np.ndarray) -> np.ndarray:
        seen.append(reverse.copy())
        return mic

    monkeypatch.setattr(controller, "process_echo_block", _process)
    controller._echo_ap = object()
    controller._echo_key = ("rate",)
    controller._render_file_key = ("rate",)
    render = np.arange(12000, dtype=np.int16)
    controller._render_samples = render
    controller._render_parsed = {"aligned": True, "started_at": 100.0, "playback_rate": 1.18}
    controller._render_paused_seconds = 0.25
    frame = np.zeros(1280, dtype=np.int16)
    out = controller.cancel_playback_echo(frame, 100.5)
    assert np.array_equal(out, frame)
    assert len(seen) == 1
    assert np.array_equal(seen[0], render[3440:4720])


@aec_required
def test_one_speech_delay_is_removed() -> None:
    speech = _tile(_wav("sentence-stop-say.wav"), 4.0)
    echo = np.zeros_like(speech)
    echo[320:] = (0.6 * speech[:-320]).astype(np.int16)
    cleaned = controller.process_echo_block(controller.make_echo_canceller(), echo, speech)
    assert _erle(echo, cleaned) >= 20.0


@aec_required
def test_two_speech_delays_beat_the_short_fit() -> None:
    # The 48-tap fit left 5.0 dB on a second arrival 20 ms later.
    speech = _tile(_wav("sentence-stop-say.wav"), 4.0)
    echo = np.zeros(len(speech), dtype=np.int32)
    echo[320:] += (0.5 * speech[:-320]).astype(np.int32)
    echo[640:] += (0.35 * speech[:-640]).astype(np.int32)
    mic = np.clip(echo, -32768, 32767).astype(np.int16)
    cleaned = controller.process_echo_block(controller.make_echo_canceller(), mic, speech)
    assert _erle(mic, cleaned) >= 12.0


@aec_required
def test_near_end_is_kept_when_it_is_not_a_copy_of_playback() -> None:
    near = _tile(_wav("good-morning-say.wav"), 4.0)
    silence = np.zeros_like(near)
    quiet = controller.process_echo_block(controller.make_echo_canceller(), near, silence)
    assert _rms(quiet[-_RATE:]) > 0.5 * _rms(near[-_RATE:])
    other = _tile(_wav("sentence-stop-say.wav"), 4.0)
    during = controller.process_echo_block(controller.make_echo_canceller(), near, other)
    assert _rms(during[-_RATE:]) > 0.5 * _rms(near[-_RATE:])


@aec_required
def test_doubletalk_keeps_the_near_end_energy() -> None:
    speech = _tile(_wav("sentence-stop-say.wav"), 4.0)
    near = _tile(_wav("good-morning-say.wav"), 4.0)
    echo = np.zeros(len(speech), dtype=np.int32)
    echo[320:] = (0.6 * speech[:-320]).astype(np.int32)
    mic = np.clip(echo + near.astype(np.int32), -32768, 32767).astype(np.int16)
    cleaned = controller.process_echo_block(controller.make_echo_canceller(), mic, speech)
    assert _rms(cleaned[-_RATE:]) > 0.4 * _rms(near[-_RATE:])


def test_cancel_uses_echo_control_and_not_the_short_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []

    def _process(_processor: object, mic: np.ndarray, _reverse: np.ndarray) -> np.ndarray:
        seen.append(len(mic))
        return mic

    def _forbid(*_args: object, **_kwargs: object) -> np.ndarray:
        raise AssertionError("short fit")

    monkeypatch.setattr(controller, "process_echo_block", _process)
    monkeypatch.setattr(controller, "apply_render_subtraction", _forbid)
    controller._echo_ap = object()
    controller._echo_key = ("clip",)
    controller._render_file_key = ("clip",)
    controller._render_samples = np.arange(8000, dtype=np.int16)
    controller._render_parsed = {"aligned": True, "started_at": 0.0, "playback_rate": 1.0}
    frame = np.zeros(1280, dtype=np.int16)
    out = controller.cancel_playback_echo(frame, 0.5)
    assert seen == [1280]
    assert np.array_equal(out, frame)


def test_a_new_clip_starts_a_new_canceller(monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[object] = []

    def _make() -> object:
        processor = object()
        made.append(processor)
        return processor

    monkeypatch.setattr(controller, "make_echo_canceller", _make)
    monkeypatch.setattr(controller, "process_echo_block", lambda _ap, mic, _rev: mic)
    controller._render_samples = np.zeros(8000, dtype=np.int16)
    controller._render_parsed = {"aligned": True, "started_at": 10.0, "playback_rate": 1.0}
    frame = np.zeros(1280, dtype=np.int16)
    controller._render_file_key = ("one",)
    controller.cancel_playback_echo(frame, 10.1)
    controller.cancel_playback_echo(frame, 10.2)
    controller._render_file_key = ("two",)
    controller.cancel_playback_echo(frame, 20.1)
    assert len(made) == 2


def test_missing_module_falls_back_to_the_short_fit(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing() -> object:
        raise ImportError("aec_audio_processing")

    monkeypatch.setattr(controller, "make_echo_canceller", _missing)
    monkeypatch.setattr(controller, "apply_render_subtraction", lambda frame, _at: frame + 1)
    controller._render_samples = np.ones(4000, dtype=np.int16)
    controller._render_parsed = {"aligned": True, "started_at": 0.0, "playback_rate": 1.0}
    controller._render_file_key = ("missing",)
    out = controller.cancel_playback_echo(np.zeros(1280, dtype=np.int16), 0.2)
    assert int(out[0]) == 1
    assert controller._echo_unavailable is True


def test_a_failed_reference_read_recovers_when_the_file_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A single unreadable WAV used to pin the render key, which left AEC dead
    # for the whole clip even after the file became readable again.
    speech = _tile(_wav("sentence-stop-say.wav"), 4.0)
    wav = tmp_path / "clip.wav"
    slot = {
        "reference": {"wav": str(wav), "sample_rate": 16000, "channels": 1, "frames": len(speech)},
        "started_at": 100.0,
        "playing": True,
        "afplay_pid": 4242,
    }
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [slot])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)

    # Stage 1: the slot announces a clip that is not readable yet. The frame
    # carrying the echo must pass through untouched, and status says so.
    fields = controller.refresh_render_reference(100.0)
    assert fields["render_connected"] is False
    block = np.zeros(1280, dtype=np.int16)
    block[:640] = 8000
    assert np.array_equal(controller.cancel_playback_echo(block, 100.0), block)

    # Stage 2: the file becomes readable. The same key must reconnect and
    # cancellation must resume on the same clip.
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(speech.tobytes())
    fields = controller.refresh_render_reference(100.1)
    assert fields["render_connected"] is True and fields["render_aligned"] is True
    echo = np.zeros(len(speech) + 320, dtype=np.int32)
    echo[320 : 320 + len(speech)] = np.rint(0.6 * speech).astype(np.int32)
    mic = np.clip(echo, -32768, 32767).astype(np.int16)
    cleaned = [
        controller.cancel_playback_echo(mic[i * 1280 : (i + 1) * 1280], 100.1 + (i + 1) * 0.08)
        for i in range(len(mic) // 1280)
    ]
    assert _erle(mic, np.concatenate(cleaned)) >= 12.0


def test_captured_frame_filters_before_vad(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, int] = {}

    def _cancel(frame: np.ndarray, captured_at: float) -> np.ndarray:
        seen["at"] = int(captured_at * 100)
        return np.full_like(frame, 7)

    def _idle(_self: object, frame: np.ndarray, *_args: object, **_kwargs: object) -> None:
        seen["idle"] = int(frame[0])

    monkeypatch.setattr(controller, "cancel_playback_echo", _cancel)
    monkeypatch.setattr(controller, "refresh_render_reference", lambda: None)
    monkeypatch.setattr(controller.MicState, "handle_idle_frame", _idle)

    class _Vad:
        def predict(self, frame: np.ndarray) -> float:
            seen["vad"] = int(frame[0])
            return 0.0

    class _Wake:
        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {}

    mic = controller.MicState()
    mic.last_manual_check = 1e12
    controller.handle_captured_frame(
        mic,
        np.zeros(1280, dtype=np.int16),
        1.25,
        "fixture",
        _Wake(),
        _Vad(),
        0.4,
        "hey_jarvis",
        0.5,
        5.0,
        15.0,
        queue.Queue(),
    )
    assert seen["at"] == 125
    assert seen["vad"] == 7
    assert seen["idle"] == 7


# Four arrivals: 15, 30, 60 and 90 ms. The short fit removes one delay. AEC3
# must keep all of them in its filter. This is a synthetic room, not the room.
_ROOM_TAPS = ((240, 0.45), (480, 0.18), (960, 0.07), (1440, 0.03))


def _room_response(reference: np.ndarray) -> np.ndarray:
    length = len(reference) + max(delay for delay, _ in _ROOM_TAPS)
    mic = np.zeros(length, dtype=np.int32)
    for delay, gain in _ROOM_TAPS:
        mic[delay : delay + len(reference)] += np.rint(gain * reference).astype(np.int32)
    return np.clip(mic, -32768, 32767).astype(np.int16)


def _mono_slot(tmp_path: Path, pcm: np.ndarray) -> dict:
    wav = tmp_path / "room-clip.wav"
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(pcm.tobytes())
    return {
        "reference": {"wav": str(wav), "sample_rate": 16000, "channels": 1, "frames": len(pcm)},
        "started_at": 100.0,
        "playing": True,
        "afplay_pid": 4242,
    }


def _feed_blocks(mic: np.ndarray) -> np.ndarray:
    cleaned: list[np.ndarray] = []
    for i in range(len(mic) // 1280):
        cleaned.append(
            controller.cancel_playback_echo(mic[i * 1280 : (i + 1) * 1280], 100.0 + (i + 1) * 0.08)
        )
    return np.concatenate(cleaned)


def _guard_window(render: np.ndarray, cursor: int, lag: int = 4800) -> np.ndarray:
    """The widened render block the guard sees for a block ending at cursor."""
    n = 1280 + 2 * lag
    origin = cursor - lag
    out = np.zeros(n, dtype=np.int16)
    lo, hi = max(0, origin), min(len(render), origin + n)
    if hi > lo:
        out[lo - origin : hi - origin] = render[lo:hi]
    return out


@aec_required
def test_a_multi_path_room_response_is_cancelled_by_aec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    speech = _tile(_wav("sentence-stop-say.wav"), 8.0)
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [_mono_slot(tmp_path, speech)])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    controller.refresh_render_reference(100.0)
    mic = _room_response(speech)
    cleaned = _feed_blocks(mic)
    print(f"multi-path ERLE: {_erle(mic, cleaned):.1f} dB")
    assert _erle(mic, cleaned) >= 10.0


def test_near_end_survives_the_multi_path_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    speech = _tile(_wav("sentence-stop-say.wav"), 8.0)
    near = _tile(_wav("good-morning-say.wav"), 8.0)
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [_mono_slot(tmp_path, speech)])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    controller.refresh_render_reference(100.0)
    mic = np.clip(_room_response(speech) + np.pad((0.7 * near).astype(np.int32), (0, max(d for d, _ in _ROOM_TAPS))), -32768, 32767).astype(np.int16)
    cleaned = _feed_blocks(mic)
    print(f"near-end kept: {_rms(cleaned[-_RATE:]) / _rms(near[-_RATE:]):.2f}")
    assert _rms(cleaned[-_RATE:]) > 0.4 * _rms(near[-_RATE:])


@aec_required
def test_the_residual_metric_reports_the_cancelled_echo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    speech = _tile(_wav("sentence-stop-say.wav"), 8.0)
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [_mono_slot(tmp_path, speech)])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    controller.refresh_render_reference(100.0)
    controller.aec_window_fields()  # reset the window
    _feed_blocks(_room_response(speech))
    fields = controller.aec_window_fields()
    print(f"window residual: {fields}")
    assert fields["aec_blocks"] > 0
    assert fields["aec_echo_db"] <= -15.0
    # The window resets: a read with no new blocks reports nothing.
    assert controller.aec_window_fields() == {}


def test_the_residual_metric_skips_silent_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        controller, "_read_playback_slots", lambda: [_mono_slot(tmp_path, np.zeros(16000, dtype=np.int16))]
    )
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    controller.refresh_render_reference(100.0)
    controller.aec_window_fields()
    rng = np.random.default_rng(7)
    mic = (rng.integers(-4000, 4000, size=12800) // 1).astype(np.int16)
    _feed_blocks(mic)
    assert controller.aec_window_fields() == {}


def test_the_canceller_still_works_after_twenty_seconds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    speech = _tile(_wav("sentence-stop-say.wav"), 20.0)
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [_mono_slot(tmp_path, speech)])
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    controller.refresh_render_reference(100.0)
    mic = _room_response(speech)
    cleaned = _feed_blocks(mic)
    print(f"20 s tail ERLE: {_erle(mic, cleaned):.1f} dB")
    assert _erle(mic, cleaned) >= 10.0


# VA-AEC-009: how far the physical echo trails the render cursor before the
# canceller stops removing it. The mic block holds the same file samples the
# controller feeds as the reverse stream, shifted back by delta_ms.
_OFFSET_DELTAS_MS = (0, 50, 100, 150, 200, 300)


def offset_residual_row(delta_ms: int, work_dir: Path, seconds: float = 2.0) -> dict:
    """Run one clip whose echo trails the render cursor by delta_ms.

    Each mic block ends at the render cursor, exactly as cancel_playback_echo
    lines its reverse block; the echo samples inside the block are that
    reverse block shifted back by delta_ms * 16. Residual dB is negative when
    the echo got smaller. Reusable from scripts/run_render_drift_probe.py.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    speech = _tile(_wav("sentence-stop-say.wav"), seconds)
    wav = work_dir / f"offset-{delta_ms}.wav"
    with wave.open(str(wav), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(_RATE)
        handle.writeframes(speech.tobytes())
    slot = {
        "reference": {"wav": str(wav), "sample_rate": _RATE, "channels": 1, "frames": len(speech)},
        "started_at": 100.0,
        "playing": True,
        "afplay_pid": 4242,
    }
    saved_slots = controller._read_playback_slots
    saved_pid = controller.pid_alive
    controller._read_playback_slots = lambda: [slot]
    controller.pid_alive = lambda _pid: True
    try:
        controller._echo_ap = None
        controller._echo_key = None
        controller._echo_unavailable = False
        controller._render_samples = None
        controller._render_parsed = None
        controller._render_file_key = None
        controller.refresh_render_reference(100.0)
        delay = delta_ms * _RATE // 1000
        echo = np.zeros(len(speech) + delay, dtype=np.int32)
        echo[delay : delay + len(speech)] += np.rint(0.6 * speech).astype(np.int32)
        mic = np.clip(echo, -32768, 32767).astype(np.int16)
        mic = mic[: (len(mic) // 1280) * 1280]
        cleaned = _feed_blocks(mic)
        return {
            "delta_ms": delta_ms,
            "residual_db": round(-_erle(mic, cleaned), 1),
            "path": "webrtc" if controller._echo_ap is not None else "short-fit",
        }
    finally:
        controller._read_playback_slots = saved_slots
        controller.pid_alive = saved_pid


@aec_required
def test_cancellation_holds_across_render_cursor_offsets(tmp_path: Path) -> None:
    rows = [offset_residual_row(delta, tmp_path) for delta in _OFFSET_DELTAS_MS]
    for row in rows:
        print(f"VA-AEC-009 offset {row['delta_ms']} ms: residual {row['residual_db']} dB via {row['path']}")
    out = Path(__file__).resolve().parents[1] / ".local" / "voice-agent" / "runs" / "VA-AEC-009-unit-table.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"id": "VA-AEC-009-unit-table", "rows": rows}, indent=2), encoding="utf-8")
    assert rows[0]["residual_db"] <= -10.0
    assert rows[-1]["residual_db"] <= -30.0
    for row in rows[1:]:
        assert row["residual_db"] <= -30.0, (
            f"offset {row['delta_ms']} ms left only {-row['residual_db']} dB of cancellation"
        )


def test_the_guard_flags_a_fit_that_removes_energy_the_reference_cannot_explain() -> None:
    # VA-INT-AUTO-040: on the fixture pipeline the warm-up filter squashed
    # stop-fixture frames from rms 4130 to rms 3 while the reference played
    # unrelated speech. The microphone block shares nothing with that block.
    near = _tile(_wav("good-morning-say.wav"), 2.0)
    reference = _tile(_wav("sentence-stop-say.wav"), 2.0)
    crushed = (near // 1000).astype(np.int16)
    assert controller.echo_over_cancels(near, crushed, reference)
    assert not controller.echo_over_cancels(near, near, reference)


def test_the_guard_trusts_a_real_delayed_echo_path() -> None:
    # The echo trails the render cursor, so the samples that produced the
    # block sit in the widened window the guard actually receives.
    speech = _tile(_wav("sentence-stop-say.wav"), 3.0)
    delay = 320
    block = speech[16000 - delay : 16000 + 1280 - delay]
    reference = _guard_window(speech, 16000)
    residual = (block // 1000).astype(np.int16)
    assert not controller.echo_over_cancels(block, residual, reference)
    assert controller.echo_over_cancels(block, residual, _tile(_wav("good-morning-say.wav"), 3.0))


def test_trailing_echo_cancels_deeper_than_zero_offset_echo(tmp_path: Path) -> None:
    # WebRTC models an echo path that trails the reference stream. An echo
    # exactly aligned with the reverse block has no delay to learn and stalls
    # near -16 dB even over 6 s. That case never happens in the room: afplay
    # startup, the output buffer, and flight time always put the speaker's
    # echo behind the cursor, and the 50-300 ms offsets cancel 36-63 dB.
    zero = offset_residual_row(0, tmp_path, seconds=6.0)
    trailing = offset_residual_row(100, tmp_path)
    print(f"VA-AEC-009 zero offset 6 s: {zero['residual_db']} dB; 100 ms trailing: {trailing['residual_db']} dB")
    assert trailing["residual_db"] <= -30.0
    assert trailing["residual_db"] < zero["residual_db"] - 10.0
