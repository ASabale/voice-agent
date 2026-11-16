#!/usr/bin/env python3
"""VA-PHYS-003 calibration: which interrupt clip shape flushes a Whisper clip
long enough for tiny.en to transcribe a clean barge token sequence?

Builds candidate clips from the recorded fixtures, scales them to the measured
speaker-to-mic attenuation (live run: file peak 25244 -> mic peak ~4284, ~0.17
of full scale), superimposes reply bleed as noise at the measured floor rms
(~150), replays bin/omp-voice-controller's exact gate/hold/flush arithmetic,
and runs faster-whisper tiny.en with the controller's initial prompt. The
probe's interrupt clip is whichever config yields all-"stop" or a
"hold on a second" token sequence.
"""

from __future__ import annotations

import json
import math
import re
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FRAME = 512
MIC_SCALE = 0.17
BLEED_RMS = 150.0
FLOOR = 148.0  # observed tts_rms_floor median during live reply runs
CONFIGS = [
    {"fixture": "stop-say", "gain": 1.2, "copies": 1, "gap": 0.0},
    {"fixture": "stop-say", "gain": 1.2, "copies": 3, "gap": 0.1},
    {"fixture": "stop-say", "gain": 1.5, "copies": 2, "gap": 0.1},
    {"fixture": "hold-on-say", "gain": 1.2, "copies": 1, "gap": 0.0},
    {"fixture": "hold-on-say", "gain": 1.5, "copies": 2, "gap": 0.3},
    {"fixture": "stop-say", "gain": 1.2, "copies": 3, "gap": 1.4},
]


def read(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)


def build(cfg: dict) -> np.ndarray:
    base = read(ROOT / "tests/fixtures" / f"{cfg['fixture']}.wav")
    b = np.clip(base * cfg["gain"], -32767, 32767)
    gap = np.zeros(int(round(cfg["gap"] * 16000)))
    parts = []
    for _ in range(cfg["copies"]):
        parts.append(b)
        if cfg["gap"] > 0:
            parts.append(gap)
    return np.concatenate(parts)


def clips_from(samples: np.ndarray, floor: float):
    gate = max(320.0, floor * 2.4)
    hot_run = 0
    held = False
    stop: list[np.ndarray] = []
    preroll: list[np.ndarray] = []
    quiet = 0
    skip = 0
    loud = 0
    voice = False
    silence = 0
    out = []
    n = len(samples)
    for i in range(0, n - FRAME + 1, FRAME):
        frame = samples[i : i + FRAME]
        rms = float(np.sqrt(np.mean(frame * frame)))
        hot = rms >= gate
        hot_run = hot_run + 1 if hot else 0
        if hot:
            preroll.append(frame)
        else:
            preroll.clear()
        just = False
        if hot_run >= 3 and not held:
            held = True
            voice = False
            quiet = 0
            skip = 2
            loud = 0
            stop = list(preroll) or [frame]
            preroll.clear()
            just = True
        keep = False
        if held and not just:
            if skip > 0:
                skip -= 1
            elif rms >= 220.0:
                loud += 1
                quiet = 0
                if loud >= 3:
                    voice = True
                keep = True
            else:
                quiet += 1
        if keep:
            silence = 0
            stop.append(frame)
            flush = len(stop) >= 10
        elif stop:
            silence += 1
            flush = silence >= 4
        else:
            flush = False
        if held and not voice and quiet >= 2 and stop:
            flush = True
        elif held and not stop and skip == 0 and quiet >= 4:
            held = False
            quiet = 0
            flush = False
        if flush and stop:
            clip = np.concatenate(stop)
            peak = float(np.max(np.abs(clip)))
            nf = len(stop)
            if 2 <= nf <= 16 and peak >= 80.0:
                a = clip.astype(np.float32) / 32768.0
                pk = float(np.max(np.abs(a)))
                if pk > 0.01:
                    a = np.clip(a * min(6.0, 0.5 / pk), -1.0, 1.0)
                out.append((nf, peak, voice, a))
            stop.clear()
            silence = 0
            held = False
            quiet = 0
            hot_run = 0
    return out


def barged(text: str) -> bool:
    tokens = [t for t in re.sub(r"[\s.,!?;:]+", " ", text.lower()).strip().split(" ") if t]
    if tokens and all(t == "stop" for t in tokens):
        return True
    if len(tokens) < 2 or tokens[0] != "hold" or tokens[1] != "on":
        return False
    return tokens[2:] in ([], ["a", "second"], ["a", "sec"], ["one", "second"], ["one", "sec"])


def main() -> int:
    from faster_whisper import WhisperModel
    whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    rng = np.random.default_rng(7)
    rows = []
    for cfg in CONFIGS:
        samples = build(cfg) * MIC_SCALE
        noise = rng.normal(0.0, BLEED_RMS, size=len(samples))
        clips = clips_from(samples + noise, FLOOR)
        heard = []
        for nf, peak, voice, a in clips:
            segs, _ = whisper.transcribe(a, language="en", initial_prompt="Hey Jarvis. stop.", beam_size=1)
            text = " ".join(s.text for s in segs)
            heard.append({"frames": nf, "peak": round(peak), "voice": voice, "text": text, "barge": barged(text)})
        hits = sum(1 for h in heard if h["barge"])
        rows.append({"config": cfg, "seconds": round(len(samples) / 16000, 2), "clips": len(heard), "hits": hits, "heard": heard})
        print(json.dumps(rows[-1]))
    out = ROOT / ".local/voice-agent/runs" / "VA-PHYS-003-WHISPER-CALIBRATION.json"
    out.write_text(json.dumps({"mic_scale": MIC_SCALE, "bleed_rms": BLEED_RMS, "floor": FLOOR, "rows": rows}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
