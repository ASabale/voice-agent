"""Unit tests for bin/voice-play: WAV parsing and live gain application.

Playback itself is stubbed; the tests exercise the parse/gain math that
per-stream ducking depends on, without touching the audio device.
"""

from __future__ import annotations

import importlib.util
import json
import struct
import types
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PLAYER = ROOT / "bin" / "voice-play"


def load_player():
    module = types.ModuleType("voice_play")
    module.__file__ = str(PLAYER)
    exec(PLAYER.read_text(encoding="utf-8"), module.__dict__)
    return module


def make_wav(path: Path, rate: int, channels: int, samples: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.astype(np.int16).tobytes())


def test_parse_wav_reads_rate_channels_and_pcm(tmp_path):
    player = load_player()
    tone = (np.sin(2 * np.pi * 440 * np.arange(24000) / 24000) * 10000).astype(np.int16)
    wav = tmp_path / "tone.wav"
    make_wav(wav, 24000, 1, tone)
    rate, channels, samples = player._parse_wav(wav.read_bytes())
    assert rate == 24000
    assert channels == 1
    assert len(samples) == 24000
    assert np.array_equal(samples.ravel(), tone)


def test_parse_wav_rejects_non_pcm_and_garbage(tmp_path):
    player = load_player()
    assert player._parse_wav(b"not a wav at all") is None
    header = bytearray(b"RIFF" + struct.pack("<I", 40) + b"WAVE")
    header += b"fmt " + struct.pack("<I", 16) + struct.pack("<HHI", 3, 1, 24000) + b"\x00" * 8
    header += b"data" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
    assert player._parse_wav(bytes(header)) is None


def test_load_gain_defaults_and_clamps(tmp_path):
    player = load_player()
    missing = tmp_path / "missing.json"
    assert player._load_gain(missing) == 1.0
    good = tmp_path / "gain.json"
    good.write_text(json.dumps({"gain": 0.35}))
    assert player._load_gain(good) == 0.35
    good.write_text(json.dumps({"gain": 3.0}))
    assert player._load_gain(good) == 1.0
    good.write_text(json.dumps({"gain": -1.0}))
    assert player._load_gain(good) == 0.0
    good.write_text("garbage")
    assert player._load_gain(good) == 1.0


def test_main_streams_gain_scaled_int16_chunks(tmp_path, monkeypatch):
    """End-to-end of main() with a stubbed output stream: catches stream
    construction mistakes (e.g. the `sr=` kwarg crash) and gain application."""
    import sys

    player = load_player()
    tone = (np.ones(2400, dtype=np.int16) * 10000)
    wav = tmp_path / "tone.wav"
    make_wav(wav, 24000, 1, tone)
    gain_file = tmp_path / "gain.json"
    gain_file.write_text(json.dumps({"gain": 0.5}))

    opened = {}
    written = []

    class FakeOut:
        def __init__(self, **kwargs):
            opened.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def write(self, chunk):
            written.append(chunk)

    monkeypatch.setattr(player.sd, "OutputStream", FakeOut)
    monkeypatch.setattr(sys, "argv", ["voice-play", str(wav), "--gain-file", str(gain_file), "--chunk-ms", "10"])
    assert player.main() == 0
    assert opened.get("samplerate") == 24000
    assert opened.get("dtype") == "int16"
    assert written, "no chunks written"
    assert all(chunk.dtype == np.int16 for chunk in written)
    assert np.all(written[0] == 5000)
    assert sum(len(c) for c in written) == 2400
