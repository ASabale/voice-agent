#!/usr/bin/env python3
"""Acoustic probe for per-stream ducking via bin/voice-play.

Plays a real VoiceBox clip twice through the speakers with `voice-play`:
once at gain 1.0, once with the gain file flipped to 0.35 mid-play.
Records the room on the mic during each run and compares echo RMS.
Verifies the macOS master volume is untouched by the duck.

Synthetic speech audio (real VoiceBox output, not a human barge-in).
Evidence: .local/voice-agent/doctor/stream-gain-probe-<ts>.json
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = ROOT / ".local" / "voice-agent" / "doctor"
GAIN_FILE = Path.home() / ".local" / "state" / "omp-voice" / "stream-gain.json"
VOICEBOX = "http://127.0.0.1:17493"
PYTHON = Path.home() / ".local" / "share" / "omp-voice" / "venv" / "bin" / "python"
PLAYER = ROOT / "bin" / "voice-play"

TEXT = "The quick brown fox jumps over the lazy dog again and again for measurement."
RECORD_SECONDS = 14.0


def master_volume() -> int:
    out = subprocess.run(
        ["osascript", "-e", "output volume of (get volume settings)"],
        capture_output=True, text=True, timeout=5,
    )
    return int(out.stdout.strip())


def profile_id() -> str:
    r = requests.get(f"{VOICEBOX}/profiles", timeout=10)
    body = r.json()
    profiles = body if isinstance(body, list) else body.get("profiles", [])
    for p in profiles:
        if p.get("name") == "Akshay":
            return p.get("id") or p.get("profile_id")
    raise SystemExit("no Akshay profile")


def make_clip() -> Path:
    payload = {
        "profile_id": profile_id(),
        "text": TEXT,
        "language": "en",
        "engine": "qwen",
        "model_size": "0.6B",
        "personality": False,
        "crossfade_ms": 25,
    }
    r = requests.post(f"{VOICEBOX}/generate/stream", json=payload, timeout=90)
    r.raise_for_status()
    path = EVIDENCE_DIR / "stream-gain-clip.wav"
    path.write_bytes(r.content)
    return path


def window_rms(rec: np.ndarray, rate: int, start_s: float, end_s: float) -> float:
    """Speech-band (300-3000 Hz) RMS over a fixed time window so the
    full-gain head of the ducked run (before the gain file flips) does not
    dominate the comparison, and low-frequency room hum is excluded."""
    a = int(start_s * rate)
    b = min(len(rec), int(end_s * rate))
    if b <= a:
        return 0.0
    seg = rec[a:b].astype(np.float64)
    spec = np.fft.rfft(seg)
    freqs = np.fft.rfftfreq(len(seg), 1 / rate)
    spec[(freqs < 300.0) | (freqs > 3000.0)] = 0
    band = np.fft.irfft(spec, n=len(seg))
    return float(np.sqrt(np.mean(band ** 2)))


def clip_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    clip = make_clip()
    clip_len = clip_duration(clip)
    rate = int(sd.query_devices(kind="input")["default_samplerate"])
    vol_before = master_volume()
    # Same [2s, clip_end] window in both runs: identical speech span, one at
    # full gain, one ducked at 0.35 from t=2 s.
    win_end = max(3.0, min(clip_len, RECORD_SECONDS - 1.0))

    GAIN_FILE.write_text(json.dumps({"gain": 1.0}))
    proc = subprocess.Popen([str(PYTHON), str(PLAYER), str(clip)])
    rec_full = sd.rec(int(RECORD_SECONDS * rate), samplerate=rate, channels=1)[:, 0]
    proc.wait(timeout=60)
    time.sleep(2)

    GAIN_FILE.write_text(json.dumps({"gain": 1.0}))
    proc = subprocess.Popen([str(PYTHON), str(PLAYER), str(clip)])
    time.sleep(2.0)  # let some full-gain echo hit the mic
    GAIN_FILE.write_text(json.dumps({"gain": 0.35}))
    rec_ducked = sd.rec(int(RECORD_SECONDS * rate), samplerate=rate, channels=1)[:, 0]
    proc.wait(timeout=60)
    time.sleep(2)

    vol_after = master_volume()
    full = window_rms(rec_full, rate, 2.0, win_end)
    ducked = window_rms(rec_ducked, rate, 2.0, win_end)
    ratio = ducked / full if full else 0.0

    result = {
        "id": "VD-DUCK-001",
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "audio": "synthetic VoiceBox clip played via voice-play (not human barge-in)",
        "record_rate_hz": rate,
        "clip_duration_s": round(clip_len, 2),
        "window_s": [2.0, round(win_end, 2)],
        "master_volume_before": vol_before,
        "master_volume_after": vol_after,
        "full_gain_window_rms": round(full, 6),
        "ducked_window_rms": round(ducked, 6),
        "echo_ratio": round(ratio, 3),
        "master_unchanged": vol_before == vol_after,
        "verdict": "stream duck works" if ratio < 0.6 and vol_before == vol_after else "inconclusive",
    }
    path = EVIDENCE_DIR / f"stream-gain-probe-{int(time.time())}.json"
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"evidence: {path}", file=sys.stderr)
    return 0 if result["verdict"] == "stream duck works" else 1


if __name__ == "__main__":
    raise SystemExit(main())
