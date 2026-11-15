#!/usr/bin/env python3
"""AEC-REAL-001 support probe: why does the live window report only -2 dB?

The live controller reports aec_echo_db near -2.6 dB while the synthetic
four-path fixture reaches -33 dB. Neither number alone says whether the
canceller is failing or the metric is diluted. This probe runs the exact
production path (refresh_render_reference -> cancel_playback_echo -> the
guard) on a real VoiceBox clip with an echo that trails the render cursor
by 0-600 ms, counts the blocks the guard returns raw, and adds a noise
variant. No microphone is opened and no sound is played; the protected
pids are never touched.

Hypotheses it can falsify:
  H1 large echo lag: cancellation collapses when the echo trails the
     cursor past the canceller's search window.
  H2 guard misfire: guard_blocks consume most of the window, so the
     window ratio is raw-echo-dominated even when the filter cancels.
  H3 metric dilution: room noise energy dwarfs the echo, bounding the
     ratio near 0 dB regardless of ERLE.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "AEC-REAL-001-LAGSWEEP"
MIC_CHUNK = 1280
MIC_RATE = 16000
PROFILE_ID = "00000000-0000-4000-8000-000000000001"  # "Akshay"
LAGS_MS = (0, 100, 200, 300, 400, 500, 600)
SECOND_TAP_MS = 150


def load_controller(state_dir: Path):
    import importlib.machinery
    import importlib.util

    os.environ["OMP_VOICE_STATE_DIR"] = str(state_dir)
    os.environ["OMP_VOICE_PLAYBACK_DIR"] = str(state_dir)
    os.environ["OMP_VOICE_PLAYBACK_PID"] = str(os.getpid())
    os.environ["OMP_VOICE_BRIDGE_ONLY"] = "http://127.0.0.1:17999"
    os.environ["OMP_VOICE_HANDY"] = "transcribe-file"
    loader = importlib.machinery.SourceFileLoader("omp_voice_lag_probe", str(ROOT / "bin" / "omp-voice-controller"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fetch_voicebox_clip(work: Path) -> Path:
    payload = json.dumps(
        {
            "profile_id": PROFILE_ID,
            "text": "The residual probe needs a sentence long enough to hold a "
            "steady echo path for several seconds while the filter adapts.",
            "language": "en",
            "engine": "qwen",
            "model_size": "0.6B",
            "personality": False,
            "crossfade_ms": 25,
        }
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:17493/generate/stream",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/octet-stream"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    path = work / "voicebox-clip.wav"
    path.write_bytes(data)
    with wave.open(str(path)) as handle:
        if handle.getnchannels() != 1:
            raise SystemExit("VoiceBox clip is not mono")
        rate = handle.getframerate()
        frames = handle.getnframes()
    if frames < 40000:
        raise SystemExit(f"clip too short: {frames} frames at {rate} Hz")
    return path


def reset_canceller(controller) -> None:
    controller._echo_ap = None
    controller._echo_key = None
    controller._aec_mic_energy = 0.0
    controller._aec_clean_energy = 0.0
    controller._aec_blocks = 0
    controller._aec_guard_blocks = 0


def rms(frame) -> float:
    import numpy as np

    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def run_lag(controller, render16: "object", started: float, lag_ms: int, noise_rms: float) -> dict:
    import numpy as np

    reset_canceller(controller)
    lag = lag_ms * MIC_RATE // 1000
    tap2 = lag + SECOND_TAP_MS * MIC_RATE // 1000
    rng = np.random.default_rng(11)
    raw_rms: list[float] = []
    clean_rms: list[float] = []
    k = 0
    total = (len(render16) + tap2) // MIC_CHUNK + 2
    while k < total:
        captured = started + (k + 1) * (MIC_CHUNK / MIC_RATE)
        pos = int((captured - started) * MIC_RATE)
        block = np.zeros(MIC_CHUNK, dtype=np.int32)
        for delay, gain in ((lag, 0.7), (tap2, 0.25)):
            end = pos - delay
            lo = max(0, end - MIC_CHUNK)
            hi = min(len(render16), end)
            if hi > lo:
                block[lo - (end - MIC_CHUNK) : hi - (end - MIC_CHUNK)] += np.rint(gain * render16[lo:hi]).astype(np.int32)
        if noise_rms > 0:
            block += np.rint(rng.normal(0, noise_rms, size=MIC_CHUNK)).astype(np.int32)
        frame = np.clip(block, -32768, 32767).astype(np.int16)
        cleaned = controller.cancel_playback_echo(frame, captured)
        raw_rms.append(rms(frame))
        clean_rms.append(rms(cleaned))
        k += 1
    fields = controller.aec_window_fields()
    return {
        "lag_ms": lag_ms,
        "noise_rms": noise_rms,
        "blocks": fields.get("aec_blocks", 0),
        "guard_blocks": fields.get("aec_guard_blocks", 0),
        "echo_db_window": fields.get("aec_echo_db"),
        "raw_rms_mean": round(sum(raw_rms) / len(raw_rms), 1) if raw_rms else None,
        "cleaned_rms_mean": round(sum(clean_rms) / len(clean_rms), 1) if clean_rms else None,
        "cleaned_rms_max": round(max(clean_rms), 1) if clean_rms else None,
    }


def main() -> int:
    work = ROOT / ".local" / "voice-agent" / "fixture-001-lag"
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)

    clip = fetch_voicebox_clip(work)
    controller = load_controller(state)

    idle_proc = subprocess.Popen(["sleep", "120"])
    try:
        with wave.open(str(clip)) as handle:
            src_rate = handle.getframerate()
            render_src = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).copy()
        render16 = controller.resample_to_mic_rate(render_src, src_rate, MIC_RATE)

        started = time.time()
        slot = {
            "reference": {
                "wav": str(clip),
                "sample_rate": src_rate,
                "channels": 1,
                "frames": len(render_src),
            },
            "started_at": started,
            "playing": True,
            "afplay_pid": idle_proc.pid,
            "playback_rate": 1.0,
        }
        (state / f"{os.getpid()}.json").write_text(json.dumps(slot), encoding="utf-8")
        controller.refresh_render_reference(started)

        parsed = controller._render_parsed
        if not parsed or not parsed.get("aligned"):
            print(json.dumps({"id": RUN_ID, "error": "render reference not aligned", "parsed": parsed}))
            return 1

        rows = [run_lag(controller, render16, started, lag, 0.0) for lag in LAGS_MS]
        noise_rows = [run_lag(controller, render16, started, lag, 60.0) for lag in (100, 200, 300)]
    finally:
        idle_proc.terminate()
        idle_proc.wait(timeout=5)

    evidence = {
        "id": RUN_ID,
        "microphone_opened": False,
        "sound_played": False,
        "clip": str(clip.relative_to(ROOT)),
        "clip_frames_16k": int(len(render16)),
        "clip_seconds": round(len(render16) / MIC_RATE, 2),
        "lag_sweep": rows,
        "noise_sweep": noise_rows,
    }
    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    # Interpretation gate: a lag that reproduces the live single-digit dB, or
    # guard blocks dominating a cancelled window, is the demonstrated cause.
    collapsed = [r for r in rows if (r["echo_db_window"] or 0) > -15.0]
    guarded = [r for r in rows if r["guard_blocks"] > 0]
    print(
        f"AEC-REAL-001 lag sweep: windows worse than -15 dB at lags "
        f"{[r['lag_ms'] for r in collapsed]}; guard-fired rows {len(guarded)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
