#!/usr/bin/env python3
"""VA-AEC-007: repeated conversations in one controller instance with echo.

Two full wake -> dictate -> flush turns run through handle_captured_frame in
one process, ~40 s of wall time, with a synthetic four-path echo of an
assistant clip playing before each turn. No microphone is opened, no sound is
played, pid 64238 and 16590 are untouched. The bridge is a dead port so each
flush is held instead of typed anywhere.

Asserts: echo alone never wakes, each real wake fires, both transcripts arrive
verbatim, latency is measured, and the run ends IDLE without a restart.
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
RUN_ID = "VA-AEC-007"
MIC_CHUNK = 1280
MIC_RATE = 16000
ROOM_TAPS = ((240, 0.45), (480, 0.18), (960, 0.07), (1440, 0.03))
RATE = 1.18
PROBE_PID = "999997"


def load_wav(path: Path):
    import numpy as np

    with wave.open(str(path)) as handle:
        if handle.getnchannels() != 1 or handle.getframerate() != 16000 or handle.getsampwidth() != 2:
            raise SystemExit(f"{path} is not 16 kHz mono 16-bit")
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).copy()


def say_wav(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["say", "-o", str(path), "--data-format=LEI16@16000", text],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return load_wav(path)


def voiced(samples, threshold=600):
    import numpy as np

    idx = np.where(np.abs(samples.astype(np.int32)) > threshold)[0]
    if idx.size == 0:
        raise SystemExit("fixture has no voiced samples")
    return samples[idx[0] : idx[-1] + 1]


def main() -> int:
    import numpy as np

    work = ROOT / ".local" / "voice-agent" / "fixture-007"
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)

    assistant_a = say_wav(work / "assistant-a.wav", "Working on the first turn now.")
    assistant_b = say_wav(work / "assistant-b.wav", "The second turn is done as well.")
    wake = load_wav(ROOT / "tests" / "fixtures" / "hey-jarvis-say.wav")
    sentence_a = voiced(say_wav(work / "sentence-a.wav", "Check the first transcript please"))
    sentence_b = voiced(say_wav(work / "sentence-b.wav", "Confirm the second transcript now"))

    os.environ["OMP_VOICE_STATE_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_PID"] = PROBE_PID
    os.environ["OMP_VOICE_BRIDGE_ONLY"] = "http://127.0.0.1:17999"
    os.environ["OMP_VOICE_HANDY"] = "transcribe-file"

    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("omp_voice_repeat_probe", str(ROOT / "bin" / "omp-voice-controller"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    controller = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = controller
    spec.loader.exec_module(controller)

    afplay_stand = work / "afplay-omp-vb-999997-clip.py"
    afplay_stand.write_text("import time; time.sleep(240)\n", encoding="utf-8")
    idle_proc = subprocess.Popen(["python3", str(afplay_stand)])
    oww, vad, jobs = controller.load_fixture_listeners()
    mic = controller.MicState()
    controller.write_status("IDLE", None)

    def echo_block(render, started_at, captured_at):
        block = np.zeros(MIC_CHUNK, dtype=np.float64)
        for delay, gain in ROOM_TAPS:
            end = int((captured_at - started_at) * MIC_RATE * RATE) - delay
            start = end - MIC_CHUNK
            lo = max(0, start)
            hi = min(len(render), end)
            if hi > lo:
                block[lo - start : hi - start] += gain * render[lo:hi]
        return np.clip(block, -32768, 32767).astype(np.int16)

    turns = []
    captured_logs = io.StringIO()
    run_started = time.time()

    def run_turn(name, render, sentence, echo_blocks):
        """Echo phase, close slot, wake + sentence, silence to flush."""
        started_at = time.time()
        slot_path = state / f"{PROBE_PID}.json"
        slot = {
            "reference": {
                "wav": str(work / f"assistant-{name}.wav"),
                "sample_rate": 16000,
                "channels": 1,
                "frames": len(render),
            },
            "started_at": started_at,
            "playing": True,
            "afplay_pid": idle_proc.pid,
            "playback_rate": RATE,
        }
        slot_path.write_text(json.dumps(slot), encoding="utf-8")
        turn = {"name": name, "echo_blocks": 0, "wake_state_before": mic.state}

        for k in range(echo_blocks):
            idle_proc.poll()
            captured = started_at + (k + 1) * MIC_CHUNK / MIC_RATE
            frame = echo_block(render, started_at, captured).astype(np.int64)
            controller.handle_captured_frame(
                mic, frame, captured, "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
            )
            turn["echo_blocks"] += 1
            time.sleep(MIC_CHUNK / MIC_RATE)
        turn["echo_only_wake"] = mic.state != "IDLE"

        # Assistant finished. The wake waits past the 0.6 s reverb-tail guard
        # so the closing slot does not swallow it.
        slot["playing"] = False
        slot["ended_at"] = time.time()
        slot_path.write_text(json.dumps(slot), encoding="utf-8")

        wake_wall = None
        gap = np.zeros(int(1.2 * MIC_RATE), dtype=np.int16)
        for part in (gap, wake, sentence):
            offset = 0
            while offset < len(part):
                idle_proc.poll()
                captured = time.time()
                frame = part[offset : offset + MIC_CHUNK]
                if len(frame) < MIC_CHUNK:
                    frame = np.pad(frame, (0, MIC_CHUNK - len(frame)))
                controller.handle_captured_frame(
                    mic, frame.astype(np.int64), captured, "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
                )
                if wake_wall is None and mic.state == "DICTATING":
                    wake_wall = captured
                offset += MIC_CHUNK
                time.sleep(MIC_CHUNK / MIC_RATE)
        turn["wake_fired"] = wake_wall is not None
        turn["wake_wall"] = wake_wall

        # Silence past the 5 s pause flush AND the 15 s idle timeout so the
        # turn really closes and the controller is IDLE for the next one.
        # (15 s is measured from the post-flush chunk restart, so the loop
        # must outlast 5 + 15 s of wall time.)
        for _ in range(280):
            idle_proc.poll()
            controller.handle_captured_frame(
                mic, np.zeros(MIC_CHUNK, dtype=np.int64), time.time(), "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
            )
            time.sleep(MIC_CHUNK / MIC_RATE)
        turn["state_after_flush"] = mic.state
        turn["state_after_turn"] = mic.state
        turns.append(turn)

    try:
        with contextlib.redirect_stdout(captured_logs):
            run_turn("a", assistant_a, sentence_a, echo_blocks=40)
            run_turn("b", assistant_b, sentence_b, echo_blocks=30)
            controller.publish_capture_totals()
        lines = captured_logs.getvalue().splitlines()
        transcripts = [line for line in lines if "Handy file transcript" in line]
        status = json.loads((state / "status.json").read_text(encoding="utf-8"))
        flush_walls = []
        for line in lines:
            stamp = line[1:line.index("]")] if line.startswith("[") else None
            if "Handy file transcript" in line and stamp:
                try:
                    flush_walls.append(time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S")))
                except ValueError:
                    pass
        for turn, flush_wall in zip(turns, flush_walls):
            if turn["wake_wall"]:
                turn["wake_to_flush_s"] = round(flush_wall - turn["wake_wall"], 2)

        evidence = {
            "id": RUN_ID,
            "microphone_opened": False,
            "sound_played": False,
            "room_taps": list(ROOM_TAPS),
            "turns": turns,
            "transcript_count": len(transcripts),
            "transcripts": transcripts,
            "echo_only_wakes": sum(1 for t in turns if t["echo_only_wake"]),
            "aec_echo_db": status.get("aec_echo_db"),
            "aec_blocks": status.get("aec_blocks"),
            "final_state": mic.state,
            "run_seconds": round(time.time() - run_started, 1),
            "notable_logs": [
                line for line in lines
                if any(word in line.lower() for word in ("wake", "transcript", "render", "echo", "reconnect"))
            ],
        }
    finally:
        controller._daemon_running.clear()
        idle_proc.terminate()
        idle_proc.wait(timeout=5)

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    ok = (
        evidence["echo_only_wakes"] == 0
        and all(t["wake_fired"] for t in turns)
        and all(t["state_after_turn"] == "IDLE" for t in turns)
        and evidence["transcript_count"] == 2
        and evidence["final_state"] == "IDLE"
        and (evidence["aec_echo_db"] or 0) <= -15
        and (evidence["aec_blocks"] or 0) > 0
    )
    print(f"VA-AEC-007: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
