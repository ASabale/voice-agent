#!/usr/bin/env python3
"""VA-AEC-006: double-talk through the production barge path.

Assistant speech plays (render slot) while the user talks over it. The mic
stream is the sum of the room echo of the assistant clip and the near-end
speech. No microphone is opened and no sound is played: the echo is
generated on the exact 16 kHz capture grid and fed through
handle_captured_frame with the real wake model, VAD, Whisper, and slot
bookkeeping. Pid 64238 and 16590 are never touched; the bridge is a dead
port so nothing is typed.
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
RUN_ID = "VA-AEC-006"
MIC_CHUNK = 1280
MIC_RATE = 16000
RATE = 1.18
ROOM_TAPS = ((240, 0.45), (480, 0.18), (960, 0.07), (1440, 0.03))
PROBE_PID = "999998"
ECHO_ONLY_BLOCKS = 40  # 3.2 s of assistant-only echo before the user talks


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


def rms(frame) -> float:
    import numpy as np

    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def main() -> int:
    import numpy as np

    work = ROOT / ".local" / "voice-agent" / "fixture-006"
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)

    assistant_clip = work / "assistant.wav"
    say_wav(assistant_clip, "The deployment manifest is loading. The sensor calibration finished overnight and the fleet is ready for the morning shift.")
    render = load_wav(assistant_clip)
    user_clip = work / "user-stop.wav"
    say_wav(user_clip, "Stop. Stop. Stop.")
    stop = load_wav(user_clip)

    os.environ["OMP_VOICE_STATE_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_DIR"] = str(state)
    os.environ["OMP_VOICE_PLAYBACK_PID"] = PROBE_PID
    os.environ["OMP_VOICE_BRIDGE_ONLY"] = "http://127.0.0.1:17999"
    os.environ["OMP_VOICE_HANDY"] = "transcribe-file"

    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("omp_voice_double_talk", str(ROOT / "bin" / "omp-voice-controller"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    controller = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = controller
    spec.loader.exec_module(controller)

    # The stand-in playback process is named like a real VoiceBox clip so
    # kill_tts_clips (which greps ps for afplay + omp-vb-<owner>-) actually
    # stops it when the barge confirms. It sleeps; it plays no sound.
    afplay_stand = work / "afplay-omp-vb-999998-clip.py"
    afplay_stand.write_text("import time; time.sleep(120)\n", encoding="utf-8")
    idle_proc = subprocess.Popen(["python3", str(afplay_stand)])
    oww, vad, jobs = controller.load_fixture_listeners()
    mic = controller.MicState()
    controller.write_status("IDLE", None)
    started_at = time.time()
    slot_path = state / f"{PROBE_PID}.json"
    slot = {
        "reference": {
            "wav": str(assistant_clip),
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

    def echo_block(captured_at: float):
        block = np.zeros(MIC_CHUNK, dtype=np.float64)
        for delay, gain in ROOM_TAPS:
            end = int((captured_at - started_at) * MIC_RATE * RATE) - delay
            start = end - MIC_CHUNK
            lo = max(0, start)
            hi = min(len(render), end)
            if hi > lo:
                block[lo - start : hi - start] += gain * render[lo:hi]
        return np.clip(block, -32768, 32767).astype(np.int16)

    def feed(blocks: int, first_block: int) -> None:
        for k in range(first_block, first_block + blocks):
            # Reap the stand-in afplay if kill_tts_clips stopped it; an
            # unreaped zombie still answers os.kill(pid, 0), which would
            # fake a playing slot.
            idle_proc.poll()
            captured = started_at + (k + 1) * MIC_CHUNK / MIC_RATE
            frame = echo_block(captured).astype(np.int64)
            if user_samples is not None:
                frame += user_samples[k * MIC_CHUNK : (k + 1) * MIC_CHUNK]
            frame = np.clip(frame, -32768, 32767).astype(np.int16)
            controller.handle_captured_frame(
                mic, frame, captured, "fixture", oww, vad, 0.40, "hey_jarvis", 0.50, 5.0, 15.0, jobs
            )
            time.sleep(MIC_CHUNK / MIC_RATE)

    # The user's "stop" arrives at block 40. `say` clips put long silence
    # around the word; the barge gate needs three consecutive hot frames, so
    # tile the voiced part back-to-back like a person repeating "stop, stop".
    voiced = np.where(np.abs(stop.astype(np.int32)) > 600)[0]
    if voiced.size == 0:
        raise SystemExit("stop fixture has no voiced samples")
    speech = np.tile(stop[voiced[0] : voiced[-1] + 1], 4)
    total_blocks = ECHO_ONLY_BLOCKS + len(speech) // MIC_CHUNK + 1 + 60
    user_samples = np.zeros(total_blocks * MIC_CHUNK, dtype=np.int64)
    offset = ECHO_ONLY_BLOCKS * MIC_CHUNK
    user_samples[offset : offset + len(speech)] = speech

    evidence = {
        "id": RUN_ID,
        "microphone_opened": False,
        "sound_played": False,
        "room_taps": list(ROOM_TAPS),
        "assistant_clip": ".local/voice-agent/fixture-006/assistant.wav",
        "playback_rate": RATE,
        "speech_start_block": ECHO_ONLY_BLOCKS,
    }
    def status_now_db() -> float | None:
        try:
            return json.loads((state / "status.json").read_text(encoding="utf-8")).get("aec_echo_db")
        except (OSError, ValueError):
            return None

    captured_logs = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_logs):
            feed(ECHO_ONLY_BLOCKS, 0)
            controller.publish_capture_totals()
            status = json.loads((state / "status.json").read_text(encoding="utf-8"))
            echo_only = captured_logs.getvalue()
            evidence["echo_only_barge_or_wake"] = any(
                word in echo_only.lower() for word in ("barge hold", "wake", "dictating")
            )
            evidence["echo_only_aec_db"] = status.get("aec_echo_db")
            evidence["echo_only_blocks"] = status.get("aec_blocks")
            evidence["state_after_echo_only"] = mic.state

            feed(total_blocks - ECHO_ONLY_BLOCKS, ECHO_ONLY_BLOCKS)
            slot_now = json.loads(slot_path.read_text(encoding="utf-8"))
            evidence["stop_heard_line"] = next(
                (line for line in captured_logs.getvalue().splitlines() if "stopping speech" in line.lower()),
                None,
            )
            evidence["playback_stopped"] = not controller.slot_is_speaking(
                slot_now, time.time(), controller.pid_alive, controller.REVERB_TAIL_GUARD_SECONDS
            )
            evidence["stand_in_afplay_exit"] = idle_proc.poll()
            evidence["vb_pids_at_stop"] = controller._omp_vb_pids()
            evidence["state_after_speech"] = mic.state
            controller.publish_capture_totals()
            evidence["double_talk_aec_db"] = status_now_db()
    finally:
        controller._daemon_running.clear()
        idle_proc.terminate()
        idle_proc.wait(timeout=5)

    def status_now_db(state_dir: Path) -> float | None:
        try:
            return json.loads((state_dir / "status.json").read_text(encoding="utf-8")).get("aec_echo_db")
        except (OSError, ValueError):
            return None

    evidence["notable_logs"] = [
        line for line in captured_logs.getvalue().splitlines()
        if any(word in line.lower() for word in ("barge", "wake", "echo", "render", "stop", "hold"))
    ]

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    ok = (
        evidence["echo_only_barge_or_wake"] is False
        and evidence["echo_only_aec_db"] is not None
        and evidence["echo_only_aec_db"] <= -15
        and evidence["stop_heard_line"] is not None
        and evidence["playback_stopped"] is True
        and evidence["state_after_speech"] != "DICTATING"
    )
    print(f"VA-AEC-006: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
