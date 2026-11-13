"""Playback slots: one session cannot clear another, and a dead player is not speaking."""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_playback", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

_VECTORS = json.loads((_PATH.parent.parent / "tests" / "playback_vectors.json").read_text(encoding="utf-8"))


def test_playback_vectors() -> None:
    for case in _VECTORS:
        alive = set(case["alive"])

        def pid_alive(pid: int, live: set[int] = alive) -> bool:
            return pid in live

        got = controller.playback_sources_speaking(
            case["slots"],
            case["legacy"],
            case["now"],
            pid_alive,
            case["tail"],
        )
        assert got is case["expect"], case["name"]


def test_bool_is_not_a_pid() -> None:
    slot = {
        "playing": True,
        "turn": 1,
        "clip": 1,
        "writer_pid": True,
        "afplay_pid": True,
        "lease_until": 10_000,
        "reason": "begin",
    }
    assert controller.slot_is_speaking(slot, 1000, lambda _pid: True, 0.6) is False


def test_slot_reference_is_the_playback_wav_description() -> None:
    ref = {
        "sample_rate": 16000,
        "channels": 1,
        "frames": 160,
        "wav": "/tmp/omp-vb-test-1.wav",
    }
    assert controller.slot_reference({"reference": ref}) == ref
    assert controller.slot_reference({"reference": {**ref, "sample_rate": True}}) is None
    assert controller.slot_reference({"playing": True}) is None


def _pcm_wav(samples: int, rate: int) -> bytes:
    data = b"\x01\x00" * samples
    header = b"RIFF" + (36 + len(data)).to_bytes(4, "little") + b"WAVEfmt "
    header += (16).to_bytes(4, "little")
    header += (1).to_bytes(2, "little")
    header += (1).to_bytes(2, "little")
    header += rate.to_bytes(4, "little")
    header += (rate * 2).to_bytes(4, "little")
    header += (2).to_bytes(2, "little")
    header += (16).to_bytes(2, "little")
    header += b"data" + len(data).to_bytes(4, "little")
    return header + data


def test_render_reference_matches_the_wav_afplay_was_given() -> None:
    wav = _pcm_wav(160, 16000)
    slot = {
        "playing": True,
        "started_at": 1000.0,
        "reference": {
            "sample_rate": 16000,
            "channels": 1,
            "frames": 160,
            "wav": "/tmp/omp-vb-test-1.wav",
        },
    }
    assert controller.render_cursor(0.0, 1.0, 16000) == 16000
    connected = controller.connect_render_reference(slot, wav, 1000.0)
    assert connected is not None
    assert connected["connected"] is True
    assert connected["aligned"] is True
    assert connected["pcm_bytes"] == 320
    assert connected["pcm"] == wav[-320:]
    assert connected["cursor"] == 0
    clamped = controller.connect_render_reference(slot, wav, 1001.0)
    assert clamped is not None
    assert clamped["cursor"] == 160
    mismatch = {**slot, "reference": {**slot["reference"], "frames": 161}}
    assert controller.connect_render_reference(mismatch, wav, 1000.0) is None
    assert controller.parse_wav_pcm(b"not a wav") is None


def test_a_delayed_copy_of_the_render_is_removed_and_noise_is_not() -> None:
    render = np.zeros(400, dtype=np.int16)
    render[100:180] = np.linspace(-8000, 8000, 80, dtype=np.int16)
    position = 150
    delay = 10
    echo = render[position - delay : position - delay + 40].astype(np.float32)
    mic = np.clip(np.rint(echo * 0.5), -32768, 32767).astype(np.int16)
    found = controller.best_render_delay(mic, render, position, 30, 0.8)
    assert found == delay
    cleaned = controller.subtract_aligned_render(mic, render, position, found)
    assert cleaned is not None
    assert int(np.max(np.abs(cleaned))) <= 1
    noise = np.random.default_rng(0).integers(-30, 30, size=40, dtype=np.int16)
    assert controller.best_render_delay(noise, render, position, 30, 0.85) is None


def test_delay_is_measured_from_the_start_of_the_block() -> None:
    block = 80
    end = 2000
    acoustic = 10
    render = np.zeros(end + 50, dtype=np.int16)
    src = end - block - acoustic
    render[src : src + block] = np.linspace(-8000, 8000, block, dtype=np.int16)
    mic = np.clip(np.rint(render[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    assert controller.best_render_delay(mic, render, end, 30, 0.8, step=8) is None
    cleaned, found = controller.remove_render_from_block(mic, render, end, 30, 0.8)
    assert found == acoustic
    assert int(np.max(np.abs(cleaned))) <= 1


def test_a_late_read_does_not_move_the_block() -> None:
    block = 80
    end = 2000
    acoustic = 10
    started = 1000.0
    captured_at = started + end / 16000
    render = np.zeros(end + 50, dtype=np.int16)
    src = end - block - acoustic
    render[src : src + block] = np.linspace(-8000, 8000, block, dtype=np.int16)
    mic = np.clip(np.rint(render[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    cleaned, found = controller.subtract_playback_at(mic, render, started, captured_at, 30, 0.8)
    assert found == acoustic
    assert int(np.max(np.abs(cleaned))) <= 1
    unchanged, missed = controller.subtract_playback_at(mic, render, started, captured_at + 0.2, 30, 0.8)
    assert missed is None
    assert np.array_equal(unchanged, mic)


def _wav_from_pcm(samples: np.ndarray, rate: int) -> bytes:
    data = np.ascontiguousarray(samples, dtype="<i2").tobytes()
    header = b"RIFF" + (36 + len(data)).to_bytes(4, "little") + b"WAVEfmt "
    header += (16).to_bytes(4, "little")
    header += (1).to_bytes(2, "little")
    header += (1).to_bytes(2, "little")
    header += rate.to_bytes(4, "little")
    header += (rate * 2).to_bytes(4, "little")
    header += (2).to_bytes(2, "little")
    header += (16).to_bytes(2, "little")
    header += b"data" + len(data).to_bytes(4, "little")
    return header + data


def test_a_mic_block_subtracts_the_slot_wav_without_waiting_for_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller, "pid_alive", lambda pid: pid == 7)
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    block = 80
    end = 2000
    acoustic = 10
    started = 1000.0
    captured_at = started + end / 16000
    render = np.zeros(end + 50, dtype=np.int16)
    src = end - block - acoustic
    render[src : src + block] = np.linspace(-8000, 8000, block, dtype=np.int16)
    wav_path = tmp_path / "clip.wav"
    wav_path.write_bytes(_wav_from_pcm(render, 16000))
    slot_dir = tmp_path / "tts-playing"
    slot_dir.mkdir()
    (slot_dir / "1.json").write_text(
        json.dumps(
            {
                "playing": True,
                "started_at": started,
                "afplay_pid": 7,
                "writer_pid": 7,
                "reference": {
                    "sample_rate": 16000,
                    "channels": 1,
                    "frames": int(render.shape[0]),
                    "wav": str(wav_path),
                },
            }
        ),
        encoding="utf-8",
    )
    mic = np.clip(np.rint(render[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    assert np.array_equal(controller.apply_render_subtraction(mic, captured_at), mic)
    controller.refresh_render_reference(started)
    cleaned = controller.apply_render_subtraction(mic, captured_at)
    assert int(np.max(np.abs(cleaned))) <= 1
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None


def test_the_newest_live_slot_is_the_render_not_the_first_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(controller, "pid_alive", lambda pid: pid == 7)
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    block = 80
    end = 2000
    acoustic = 10
    started = 1000.0
    captured_at = started + end / 16000
    older_pcm = np.zeros(end + 50, dtype=np.int16)
    newer_pcm = np.zeros(end + 50, dtype=np.int16)
    src = end - block - acoustic
    newer_pcm[src : src + block] = np.linspace(-8000, 8000, block, dtype=np.int16)
    older_path = tmp_path / "older.wav"
    newer_path = tmp_path / "newer.wav"
    older_path.write_bytes(_wav_from_pcm(older_pcm, 16000))
    newer_path.write_bytes(_wav_from_pcm(newer_pcm, 16000))

    def slot(path: Path, started_at: float, afplay: int) -> dict:
        return {
            "playing": True,
            "started_at": started_at,
            "afplay_pid": afplay,
            "writer_pid": 7,
            "reference": {
                "sample_rate": 16000,
                "channels": 1,
                "frames": end + 50,
                "wav": str(path),
            },
        }

    older = slot(older_path, started - 5, 7)
    newer_dead = slot(newer_path, started + 5, 99)
    newer_live = slot(newer_path, started, 7)
    assert controller.choose_render_slot([older, newer_dead, newer_live], started, controller.pid_alive) is newer_live
    assert controller.choose_render_slot([newer_dead, older], started, controller.pid_alive) is older
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [older, newer_live])
    controller.refresh_render_reference(started)
    mic = np.clip(np.rint(newer_pcm[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    cleaned = controller.apply_render_subtraction(mic, captured_at)
    assert int(np.max(np.abs(cleaned))) <= 1
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None


def test_afplay_rate_advances_the_file_faster_than_the_wall_clock() -> None:
    assert controller.render_cursor(0.0, 1.0, 16000) == 16000
    assert controller.render_cursor(0.0, 1.0, 16000, 2.0) == 32000
    assert controller.playback_rate_of({}) == 1.0
    assert controller.playback_rate_of({"playback_rate": 1.18}) == 1.18
    assert controller.playback_rate_of({"playback_rate": True}) == 1.0
    assert controller.playback_rate_of({"playback_rate": 3}) == 1.0
    block = 80
    acoustic = 10
    started = 1000.0
    captured_at = started + 0.125
    end = 4000
    render = np.zeros(end + 50, dtype=np.int16)
    src = end - block - acoustic
    render[src : src + block] = np.linspace(-8000, 8000, block, dtype=np.int16)
    mic = np.clip(np.rint(render[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    _unchanged, missed = controller.subtract_playback_at(mic, render, started, captured_at, 30, 0.8)
    assert missed is None
    cleaned, found = controller.subtract_playback_at(
        mic, render, started, captured_at, 30, 0.8, playback_rate=2.0
    )
    assert found == acoustic
    assert int(np.max(np.abs(cleaned))) <= 1


def test_a_22050_hz_clip_is_subtracted_on_the_microphone_grid(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(controller, "pid_alive", lambda pid: pid == 7)
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    block = 80
    end = 2000
    acoustic = 10
    started = 1000.0
    captured_at = started + end / 16000
    mic_grid = np.zeros(end + 50, dtype=np.int16)
    src = end - block - acoustic
    span = slice(src - 30, src + block + 30)
    mic_grid[span] = np.linspace(-8000, 8000, span.stop - span.start, dtype=np.int16)
    file_len = int(np.ceil(len(mic_grid) * 22050 / 16000)) + 1
    pos = np.arange(file_len, dtype=np.float64) * (16000 / 22050)
    i0 = np.minimum(np.floor(pos).astype(np.int64), len(mic_grid) - 1)
    i1 = np.minimum(i0 + 1, len(mic_grid) - 1)
    frac = (pos - i0).astype(np.float32)
    file_pcm = np.clip(
        np.rint(mic_grid[i0].astype(np.float32) * (1.0 - frac) + mic_grid[i1].astype(np.float32) * frac),
        -32768,
        32767,
    ).astype(np.int16)
    same = np.array([1, 2, 3], dtype=np.int16)
    assert np.array_equal(controller.resample_to_mic_rate(same, 16000), same)
    assert controller.resample_to_mic_rate(file_pcm, 22050).shape == (int(len(file_pcm) * 16000 / 22050),)
    wav_path = tmp_path / "clip-22050.wav"
    wav_path.write_bytes(_wav_from_pcm(file_pcm, 22050))
    slot = {
        "playing": True,
        "started_at": started,
        "afplay_pid": 7,
        "writer_pid": 7,
        "reference": {
            "sample_rate": 22050,
            "channels": 1,
            "frames": int(file_pcm.shape[0]),
            "wav": str(wav_path),
        },
    }
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: [slot])
    mic = np.clip(np.rint(mic_grid[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    controller.refresh_render_reference(started)
    assert controller._render_parsed is not None
    assert controller._render_parsed["sample_rate"] == 22050
    assert controller._render_parsed["aligned"] is True
    cleaned = controller.apply_render_subtraction(mic, captured_at)
    assert int(np.max(np.abs(cleaned))) <= 2
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None


def test_a_filtered_copy_between_coarse_steps_is_removed() -> None:
    rng = np.random.default_rng(0)
    render = rng.integers(-8000, 8000, size=4000, dtype=np.int16)
    end = 2000
    block = 80
    acoustic = 10
    origin = end - block
    mixed = (
        0.40 * render[origin - acoustic : origin - acoustic + block].astype(np.float32)
        + 0.25 * render[origin - acoustic - 1 : origin - acoustic - 1 + block].astype(np.float32)
        + 0.15 * render[origin - acoustic - 2 : origin - acoustic - 2 + block].astype(np.float32)
    )
    mic = np.clip(np.rint(mixed), -32768, 32767).astype(np.int16)
    assert controller.best_render_delay(mic, render, origin, 30, 0.75, step=8) is None
    cleaned, found = controller.remove_render_from_block(mic, render, end, 30, 0.75)
    assert found == acoustic
    assert int(np.max(np.abs(cleaned))) <= 1


def test_the_clip_is_still_subtracted_during_the_reverb_tail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(controller, "pid_alive", lambda pid: pid == 7)
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    controller._render_hold_until = 0.0
    block = 80
    end = 2000
    acoustic = 10
    started = 1000.0
    captured_at = started + end / 16000
    render = np.zeros(end + 50, dtype=np.int16)
    src = end - block - acoustic
    render[src : src + block] = np.linspace(-8000, 8000, block, dtype=np.int16)
    wav_path = tmp_path / "clip.wav"
    wav_path.write_bytes(_wav_from_pcm(render, 16000))
    slot = {
        "playing": True,
        "started_at": started,
        "afplay_pid": 7,
        "writer_pid": 7,
        "reference": {
            "sample_rate": 16000,
            "channels": 1,
            "frames": int(render.shape[0]),
            "wav": str(wav_path),
        },
    }
    slots = {"items": [slot]}
    monkeypatch.setattr(controller, "_read_playback_slots", lambda: slots["items"])
    mic = np.clip(np.rint(render[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    controller.refresh_render_reference(started)
    wav_path.unlink()
    slots["items"] = []
    controller.refresh_render_reference(started + 0.2)
    cleaned = controller.apply_render_subtraction(mic, captured_at)
    assert int(np.max(np.abs(cleaned))) <= 1
    controller.refresh_render_reference(started + 0.2 + controller.REVERB_TAIL_GUARD_SECONDS)
    assert np.array_equal(controller.apply_render_subtraction(mic, captured_at), mic)
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    controller._render_hold_until = 0.0


def test_taps_cover_the_arrival_before_the_correlation_peak() -> None:
    rng = np.random.default_rng(0)
    white = rng.normal(0, 1, size=8000)
    kernel = np.array([1, 2, 3, 4, 3, 2, 1], dtype=np.float64)
    kernel /= kernel.sum()
    smooth = np.convolve(white, kernel, mode="same")
    smooth = smooth / np.max(np.abs(smooth)) * 8000
    render = np.clip(np.rint(smooth), -32768, 32767).astype(np.int16)
    end = 4000
    block = 1280
    first = 20
    origin = end - block
    mixed = (
        0.45 * render[origin - first : origin - first + block].astype(np.float64)
        + 0.30 * render[origin - first - 1 : origin - first - 1 + block].astype(np.float64)
        + 0.15 * render[origin - first - 2 : origin - first - 2 + block].astype(np.float64)
    )
    mic = np.clip(np.rint(mixed), -32768, 32767).astype(np.int16)
    peak = controller.best_render_delay(mic, render, origin, 2400, 0.75, step=1)
    assert peak is not None and peak != first
    cleaned, found = controller.remove_render_from_block(mic, render, end, 2400, 0.75)
    assert found == peak
    assert int(np.max(np.abs(cleaned))) <= 1


def test_the_start_of_a_clip_is_subtracted_before_a_whole_block_fits() -> None:
    rng = np.random.default_rng(1)
    render = rng.integers(-4000, 4000, size=8000, dtype=np.int16)
    block = 1280
    elapsed = 400
    mic = np.zeros(block, dtype=np.int16)
    heard = np.clip(np.rint(render[:elapsed].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    mic[block - elapsed :] = heard
    cleaned, found = controller.remove_render_from_block(mic, render, elapsed, 2400, 0.75)
    assert found == 0
    assert int(np.max(np.abs(cleaned[: block - elapsed]))) == 0
    assert int(np.max(np.abs(cleaned[block - elapsed :]))) <= 1


def test_a_two_millisecond_smear_is_not_removed_by_eight_taps() -> None:
    rng = np.random.default_rng(2)
    white = rng.normal(0, 1, size=16000)
    kernel = np.array([1, 2, 3, 4, 3, 2, 1], dtype=np.float64)
    kernel /= kernel.sum()
    smooth = np.convolve(white, kernel, mode="same")
    smooth = smooth / np.max(np.abs(smooth)) * 6000
    render = np.clip(np.rint(smooth), -32768, 32767).astype(np.int16)
    decay = np.exp(-np.arange(32) / 8.0)
    decay /= decay.sum()
    end = 8000
    block = 1280
    acoustic = 30
    origin = end - block
    mixed = np.zeros(block, dtype=np.float64)
    for lag, weight in enumerate(decay):
        mixed += weight * render[origin - acoustic - lag : origin - acoustic - lag + block]
    mic = np.clip(np.rint(mixed * (175 / np.sqrt(np.mean(mixed**2)))), -32768, 32767).astype(np.int16)
    peak = controller.best_render_delay(mic, render, origin, 2400, 0.75, step=1)
    assert peak is not None
    short = controller.subtract_render_filter(mic, render, origin, peak, taps=8)
    assert short is not None
    short_rms = float(np.sqrt(np.mean(short.astype(np.float32) ** 2)))
    assert short_rms > 40
    cleaned, found = controller.remove_render_from_block(mic, render, end, 2400, 0.75)
    assert found == peak
    assert float(np.sqrt(np.mean(cleaned.astype(np.float32) ** 2))) < 5


def test_a_paused_afplay_does_not_advance_the_file_cursor() -> None:
    controller._render_paused_at = None
    controller._render_paused_seconds = 0.0
    started = 1000.0
    controller.note_render_paused(started + 0.5)
    controller.note_render_resumed(started + 0.75)
    assert controller.paused_playback_seconds(started + 1.0) == 0.25
    block = 80
    acoustic = 10
    played = int(0.75 * 16000)
    render = np.zeros(played + 500, dtype=np.int16)
    src = played - block - acoustic
    render[src : src + block] = np.linspace(-8000, 8000, block, dtype=np.int16)
    mic = np.clip(np.rint(render[src : src + block].astype(np.float32) * 0.5), -32768, 32767).astype(np.int16)
    missed, no_delay = controller.subtract_playback_at(mic, render, started, started + 1.0, 30, 0.8)
    assert no_delay is None
    cleaned, found = controller.subtract_playback_at(
        mic, render, started, started + 1.0, 30, 0.8, paused_seconds=0.25
    )
    assert found == acoustic
    assert int(np.max(np.abs(cleaned))) <= 1
    controller._render_paused_at = None
    controller._render_paused_seconds = 0.0


def test_a_paused_afplay_does_not_advance_the_published_cursor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller, "pid_alive", lambda pid: pid in {11, 22})
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    controller._render_paused_at = None
    controller._render_paused_seconds = 0.0
    started = 1000.0
    frames = 16000
    wav_path = tmp_path / "clip.wav"
    wav_path.write_bytes(_wav_from_pcm(np.zeros(frames, dtype=np.int16), 16000))
    slot_dir = tmp_path / "tts-playing"
    slot_dir.mkdir()
    (slot_dir / "11.json").write_text(
        json.dumps(
            {
                "playing": True,
                "started_at": started,
                "turn": 1,
                "clip": 1,
                "writer_pid": 11,
                "afplay_pid": 22,
                "lease_until": started + 60,
                "reference": {
                    "sample_rate": 16000,
                    "channels": 1,
                    "frames": frames,
                    "wav": str(wav_path),
                },
            }
        ),
        encoding="utf-8",
    )
    at_pause = controller.refresh_render_reference(started + 0.50)
    assert at_pause["render_cursor"] == 8000
    controller.note_render_paused(started + 0.50)
    while_stopped = controller.refresh_render_reference(started + 0.75)
    assert controller.paused_playback_seconds(started + 0.75) == 0.25
    assert while_stopped["render_cursor"] == 8000
    controller.note_render_resumed(started + 0.75)
    after_resume = controller.refresh_render_reference(started + 1.0)
    assert after_resume["render_cursor"] == 12000
    controller._render_samples = None
    controller._render_parsed = None
    controller._render_file_key = None
    controller._render_paused_at = None
    controller._render_paused_seconds = 0.0
