#!/usr/bin/env python3
"""VA-AEC-008: the render reference dies mid-playback and the loop recovers.

Mid-conversation, VoiceBox's clip file disappears while the slot still says
"playing" (a crashed writer or a cleanup race). The production frame loop
must survive it: no exception, the status says the render reference is
unavailable, echo blocks flow through uncancelled without waking the mic,
and when a fresh valid clip appears the canceller reconnects and cancels
again. No microphone is opened, no sound is played; pid 64238 and 16590 are
untouched; the bridge is a dead port so nothing is typed.
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
RUN_ID = "VA-AEC-008"
MIC_CHUNK = 1280
MIC_RATE = 16000
ROOM_TAPS = ((240, 0.45), (480, 0.18), (960, 0.07), (1440, 0.03))
RATE = 1.18
PROBE_PID = "999996"


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

    work = ROOT / ".local" / "voice-agent" / "fixture-008"
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)

    clip_one = work / "assistant-one.wav"
    render_one = say_wav(clip_one, "The first render reference is about to disappear from disk.")
    clip_two = work / "assistant-two.wav"
    render_two = say_wav(clip_two, "The replacement reference plays and cancels again.")
    wake = load_wav(ROOT / "tests" / "fixtures" / "hey-jarvis-say.wav")
    sentence = voiced(say_wav(work / "sentence.wav", "Confirm the recovery transcript"))

    os.environ["OMP_VOICE_STATE_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_PID"] = PROBE_PID
    os.environ["OMP_VOICE_BRIDGE_ONLY"] = "http://127.0.0.1:17999"
    os.environ["OMP_VOICE_HANDY"] = "transcribe-file"

    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("omp_voice_render_recovery", str(ROOT / "bin" / "omp-voice-controller"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    controller = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = controller
    spec.loader.exec_module(controller)

    afplay_stand = work / "afplay-omp-vb-999996-clip.py"
    afplay_stand.write_text("import time; time.sleep(240)\n", encoding="utf8")
    idle_proc = subprocess.Popen(["python3", str(afplay_stand)])
    oww, vad, jobs = controller.load_fixture_listeners()
    mic = controller.MicState()
    controller.write_status("IDLE", None)

    slot_path = state / f"{PROBE_PID}.json"

    def open_slot(wav: Path, render):
        started_at = time.time()
        slot = {
            "reference": {
                "wav": str(wav),
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
        return slot, started_at

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

    def feed(render, started_at, blocks):
        for k in range(blocks):
            idle_proc.poll()
            captured = started_at + (k + 1) * MIC_CHUNK / MIC_RATE
            frame = echo_block(render, started_at, captured).astype(np.int64)
            controller.handle_captured_frame(
                mic, frame, captured, "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
            )
            time.sleep(MIC_CHUNK / MIC_RATE)

    def status():
        try:
            return json.loads((state / "status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    evidence = {"id": RUN_ID, "microphone_opened": False, "sound_played": False}
    captured_logs = io.StringIO()
    run_started = time.time()
    try:
        with contextlib.redirect_stdout(captured_logs):
            # 1. Valid reference playing: the canceller is connected.
            slot, started = open_slot(clip_one, render_one)
            feed(render_one, started, 25)
            controller.publish_capture_totals()
            evidence["before_failure"] = {
                "render_connected": status().get("render_connected"),
                "aec_echo_db": status().get("aec_echo_db"),
                "aec_blocks": status().get("aec_blocks"),
            }

            # 2. The writer crashes mid-render: the slot announces the full
            # clip but the file on disk is truncated. The header no longer
            # matches the slot, so the canceller must refuse the reference,
            # pass echo through uncancelled, and stay alive.
            partial = clip_one.with_suffix(".partial.wav")
            header_and_half = clip_one.read_bytes()[: 44 + len(render_one) * 2 // 2]
            partial.write_bytes(header_and_half)
            slot["reference"]["wav"] = str(partial)
            slot_path.write_text(json.dumps(slot), encoding="utf-8")
            feed(render_one, started, 25)
            controller.publish_capture_totals()
            evidence["during_failure"] = {
                "render_connected": status().get("render_connected"),
                "mic_state": mic.state,
                "exception": None,
            }

            # 3. A fresh valid clip arrives (VoiceBox recovered). The
            # canceller must reconnect and cancel again.
            slot, started = open_slot(clip_two, render_two)
            feed(render_two, started, 25)
            controller.publish_capture_totals()
            evidence["after_reconnect"] = {
                "render_connected": status().get("render_connected"),
                "aec_echo_db": status().get("aec_echo_db"),
                "aec_blocks": status().get("aec_blocks"),
            }

            # 4. Close the slot, wake, dictate, flush: the conversation
            # continued after the failure.
            slot["playing"] = False
            slot["ended_at"] = time.time()
            slot_path.write_text(json.dumps(slot), encoding="utf-8")
            gap = np.zeros(int(1.2 * MIC_RATE), dtype=np.int16)
            wake_wall = None
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
            for _ in range(280):
                idle_proc.poll()
                controller.handle_captured_frame(
                    mic, np.zeros(MIC_CHUNK, dtype=np.int64), time.time(), "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
                )
                time.sleep(MIC_CHUNK / MIC_RATE)
            evidence["wake_fired"] = wake_wall is not None
            evidence["final_state"] = mic.state
            evidence["notable_logs"] = [
                line for line in captured_logs.getvalue().splitlines()
                if any(word in line.lower() for word in ("render", "echo", "wake", "transcript", "hold"))
            ]
            evidence["run_seconds"] = round(time.time() - run_started, 1)
    finally:
        controller._daemon_running.clear()
        idle_proc.terminate()
        idle_proc.wait(timeout=5)

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    before = evidence["before_failure"]
    during = evidence["during_failure"]
    after = evidence["after_reconnect"]
    ok = (
        before["render_connected"] is True
        and (before["aec_echo_db"] or 0) <= -15
        and during["render_connected"] is False
        and during["mic_state"] == "IDLE"
        and after["render_connected"] is True
        and (after["aec_echo_db"] or 0) <= -15
        and after["aec_blocks"] > 0
        and evidence["wake_fired"]
        and evidence["final_state"] == "IDLE"
        and any("render reference unavailable" in line.lower() for line in evidence["notable_logs"])
    )
    print(f"VA-AEC-008: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
