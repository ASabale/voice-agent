#!/usr/bin/env python3
"""VA-AEC-005: fixture-fed echo through the production frame loop.

Feeds a synthetic four-path room echo of the wake clip through
handle_captured_frame with the real openwakeword, VAD, and Handy file
transcription. No microphone is opened, no sound is played, and pid 64238
and 16590 are never touched. The bridge is pointed at a dead port so a
flush is held instead of typed anywhere.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "VA-AEC-005"
MIC_CHUNK = 1280
MIC_RATE = 16000
ROOM_TAPS = ((240, 0.45), (480, 0.18), (960, 0.07), (1440, 0.03))
PROBE_PID = "999999"


def load_wav(path: Path):
    import numpy as np

    with wave.open(str(path)) as handle:
        if handle.getnchannels() != 1 or handle.getframerate() != 16000 or handle.getsampwidth() != 2:
            raise SystemExit(f"{path} is not 16 kHz mono 16-bit")
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).copy()


def say_wav(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["say", "-o", str(path), "--data-format=LEI16@16000", text],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def echo_block(render, started_at: float, captured_at: float, rate: float):
    import numpy as np

    block = np.zeros(MIC_CHUNK, dtype=np.float64)
    for delay, gain in ROOM_TAPS:
        end = int((captured_at - started_at) * MIC_RATE * rate) - delay
        start = end - MIC_CHUNK
        lo = max(0, start)
        hi = min(len(render), end)
        if hi > lo:
            block[lo - start : hi - start] += gain * render[lo:hi]
    return np.clip(block, -32768, 32767).astype(np.int16)


def rms(frame) -> float:
    import numpy as np

    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def main() -> int:
    import numpy as np

    work = ROOT / ".local" / "voice-agent" / "fixture-005"
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)

    render_clip = work / "render-echo.wav"
    say_wav(render_clip, "Hey Jarvis. Hey Jarvis. Hey Jarvis. Hey Jarvis.")
    render = load_wav(render_clip)
    wake = load_wav(ROOT / "tests" / "fixtures" / "hey-jarvis-say.wav")
    utterance = say_wav(work / "near-end.wav", "The echo probe recorded clearly.")
    near = load_wav(work / "near-end.wav")

    os.environ["OMP_VOICE_STATE_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_PID"] = PROBE_PID
    os.environ["OMP_VOICE_BRIDGE_ONLY"] = "http://127.0.0.1:17999"
    os.environ["OMP_VOICE_HANDY"] = "transcribe-file"

    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("omp_voice_aec_probe", str(ROOT / "bin" / "omp-voice-controller"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    controller = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = controller
    spec.loader.exec_module(controller)

    # A real, alive pid stands in for afplay so the slot counts as playing
    # without any sound reaching the room. The slot is written only after the
    # models load so the echo phase starts while the clip is still "playing".
    idle_proc = subprocess.Popen(["sleep", "60"])
    oww, vad, jobs = controller.load_fixture_listeners()
    mic = controller.MicState()
    controller.write_status("IDLE", None)
    started_at = time.time()
    slot = {
        "reference": {
            "wav": str(render_clip),
            "sample_rate": 16000,
            "channels": 1,
            "frames": len(render),
        },
        "started_at": started_at,
        "playing": True,
        "afplay_pid": idle_proc.pid,
        "playback_rate": 1.18,
    }
    (state / f"{PROBE_PID}.json").write_text(json.dumps(slot), encoding="utf-8")

    evidence = {
        "id": RUN_ID,
        "microphone_opened": False,
        "sound_played": False,
        "room_taps": list(ROOM_TAPS),
        "render_clip": ".local/voice-agent/fixture-005/render-echo.wav",
        "playback_rate": 1.18,
    }
    captured_logs = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_logs):
            # Phase 1: echo only. The speaker is "playing"; the user says
            # nothing. Blocks land on the exact 16 kHz grid so the mic stream
            # is contiguous, like a real capture loop.
            raw_echo = 0.0
            echo_frames = 0
            advance = MIC_CHUNK / (MIC_RATE * 1.18)
            end = started_at + len(render) / (MIC_RATE * 1.18) + 1440 / MIC_RATE + 0.2
            k = 0
            while True:
                captured = started_at + (k + 1) * advance
                if captured > end:
                    break
                frame = echo_block(render, started_at, captured, 1.18)
                raw_echo += rms(frame)
                echo_frames += 1
                controller.handle_captured_frame(
                    mic, frame, captured, "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
                )
                k += 1
                time.sleep(MIC_CHUNK / MIC_RATE)
            controller.publish_capture_totals()
            status = json.loads((state / "status.json").read_text(encoding="utf-8"))
            evidence["echo_phase_seconds"] = round(time.time() - started_at, 2)
            evidence["echo_raw_rms"] = round(raw_echo / echo_frames, 1)
            evidence["wake_fired_on_echo_only"] = mic.state != "IDLE"
            evidence["aec_echo_db"] = status.get("aec_echo_db")
            evidence["aec_blocks"] = status.get("aec_blocks")
            evidence["state_after_echo"] = mic.state

            # The assistant clip has ended: close the slot so the near-end
            # utterance is not swallowed by the barge logic.
            slot["playing"] = False
            slot["ended_at"] = time.time()
            (state / f"{PROBE_PID}.json").write_text(json.dumps(slot), encoding="utf-8")

            # Phase 2: the real wake word and a near-end utterance, then
            # silence long enough to flush.
            feed = [(np.zeros(3200, dtype=np.int16), 0.0), (wake, 0.4), (near, 0.2)]
            source = controller.FixtureAudioSource(feed, pace=True)
            with source:
                while True:
                    frame = source.read()
                    if frame is None:
                        break
                    controller.handle_captured_frame(
                        mic, frame, time.time(), "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
                    )
            evidence["wake_fired_on_near_end"] = mic.state == "DICTATING"
            silence = controller.FixtureAudioSource([(np.zeros(MIC_RATE, dtype=np.int16), 0.0)] * 7, pace=True)
            with silence:
                while True:
                    frame = silence.read()
                    if frame is None:
                        break
                    controller.handle_captured_frame(
                        mic, frame, time.time(), "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
                    )
        transcript = None
        for line in captured_logs.getvalue().splitlines():
            if "Handy file transcript" in line:
                transcript = line
        evidence["transcript_line"] = transcript
        evidence["state_after_flush"] = mic.state
        evidence["notable_logs"] = [
            line for line in captured_logs.getvalue().splitlines()
            if any(word in line.lower() for word in ("wake", "barge", "transcript", "echo", "render", "hold"))
        ]
    finally:
        controller._daemon_running.clear()
        idle_proc.terminate()
        idle_proc.wait(timeout=5)

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    ok = (
        evidence["wake_fired_on_echo_only"] is False
        and evidence["wake_fired_on_near_end"] is True
        and transcript is not None
        and (evidence["aec_echo_db"] or 0) <= -15
        and (evidence["aec_blocks"] or 0) > 0
    )
    print(f"VA-AEC-005: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
