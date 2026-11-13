"""WebRTC echo control on the playback reference. Not the microphone."""

import importlib.machinery
import importlib.util
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


def test_one_speech_delay_is_removed() -> None:
    speech = _tile(_wav("sentence-stop-say.wav"), 4.0)
    echo = np.zeros_like(speech)
    echo[320:] = (0.6 * speech[:-320]).astype(np.int16)
    cleaned = controller.process_echo_block(controller.make_echo_canceller(), echo, speech)
    assert _erle(echo, cleaned) >= 20.0


def test_two_speech_delays_beat_the_short_fit() -> None:
    # The 48-tap fit left 5.0 dB on a second arrival 20 ms later.
    speech = _tile(_wav("sentence-stop-say.wav"), 4.0)
    echo = np.zeros(len(speech), dtype=np.int32)
    echo[320:] += (0.5 * speech[:-320]).astype(np.int32)
    echo[640:] += (0.35 * speech[:-640]).astype(np.int32)
    mic = np.clip(echo, -32768, 32767).astype(np.int16)
    cleaned = controller.process_echo_block(controller.make_echo_canceller(), mic, speech)
    assert _erle(mic, cleaned) >= 12.0


def test_near_end_is_kept_when_it_is_not_a_copy_of_playback() -> None:
    near = _tile(_wav("good-morning-say.wav"), 4.0)
    silence = np.zeros_like(near)
    quiet = controller.process_echo_block(controller.make_echo_canceller(), near, silence)
    assert _rms(quiet[-_RATE:]) > 0.5 * _rms(near[-_RATE:])
    other = _tile(_wav("sentence-stop-say.wav"), 4.0)
    during = controller.process_echo_block(controller.make_echo_canceller(), near, other)
    assert _rms(during[-_RATE:]) > 0.5 * _rms(near[-_RATE:])


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
