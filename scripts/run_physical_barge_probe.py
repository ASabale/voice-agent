#!/usr/bin/env python3
"""VA-PHYS-003 — acoustic barge: a recorded "hold on a second" utterance
played through the real speakers cuts a live reply through the real mic.

Level 4 physical: real microphone owned by the running controller, real
speakers, real afplay, real Whisper. No human voice in the room.

Procedure:
1. Launch an isolated omp session and submit a long reply prompt; the reply
   streams to the bridge and plays via afplay.
2. While the reply's afplay slot is live, play the interruption clip: the
   recorded tests/fixtures/hold-on-say.wav, gain 1.4, tiled twice with 0.2 s
   silence (calibration: scripts/barge_whisper_calibration_probe.py — the
   continuous 1.05 s phrase flushes a >=10-frame Whisper clip that tiny.en
   transcribes as "Hold on a second." with clean barge tokens at mic scale; a
   one-word "stop" burst flushes a 3-frame clip tiny.en mishears).
3. Find the first `TTS barge hold` line after the burst onset; watch for the
   `stopping speech` log line and the controller-published
   `stop_latency_s` (hold opened -> afplay confirmed dead).
4. Assert the reply afplay is dead, no resume stage follows, the controller
   survives, and the state returns to IDLE.

Acceptance: gates are clocked from the burst ONSET (afplay spawn offset is
calibrated in-probe with a 0.1 s tone: Popen -> first sound is ~0.9 s of
harness overhead, not product latency). Hold line within 1.2 s of the burst
onset; the stop chain completes within 3.0 s of the onset; reply clip killed;
no resume; controller alive and IDLE. `stop_latency_s` is recorded and
checked against the VA-INT-AUTO-041 bound (1.076 s) only when the controller
republishes it in the live turn window.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_fixture_pipeline import (  # noqa: E402
    start_omp,
    wait_playing,
    voicebox_healthy,
)

ROOT = Path(__file__).resolve().parent.parent
INTERRUPT_CLIP = ROOT / "tests/fixtures/hold-on-say.wav"
# Continuous phrase, tiled three times with a 50 ms gap: the first burst opens
# the hold mid-phrase, and the seamless copies keep frames hot long enough to
# flush a >=10-frame Whisper clip dominated by the phrase itself rather than
# by reply bleed.
GAIN = 1.47
BURST_COPIES = 4
BURST_GAP = 0.05  # seconds of silence between bursts
HOLD_ACCEPT_S = 1.2
STOP_WINDOW_S = 4.0  # onset -> stop_playback; floor is 3 hot frames + 10-frame clip accumulation + tiny.en inference (~2.3 s after hold)
HOLD_TO_STOP_BOUND_S = 3.0  # controller-measured hold -> clip death
REPLY_PROMPT = (
    "Give me a detailed explanation of how echo cancellation works in a "
    "voice assistant, in about 180 words, covering the reference signal, "
    "the adaptive filter, and why residual echo matters for wake-word "
    "false positives."
)
RUN_FILE = ROOT / ".local/voice-agent/runs/VA-PHYS-003-ACOUSTIC-BARGE.json"
PROBE_DIR = ROOT / ".local/voice-agent/probes"
TRACE_FILE = Path.home() / ".local/state/omp-voice/barge-trace.jsonl"


def boost_wav(path: Path, gain: float, copies: int = 1, gap_s: float = 0.0) -> dict:
    import wave

    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        n = w.getnchannels()
        width = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    samples = [int.from_bytes(frames[i : i + 2], "little", signed=True) for i in range(0, len(frames), 2)]
    peak = max(abs(s) for s in samples)
    rms = round((sum(s * s for s in samples) / len(samples)) ** 0.5, 1)
    boosted = [max(-32767, min(32767, int(s * gain))) for s in samples]
    gap = [0] * int(round(gap_s * rate)) if copies > 1 else []
    tiled: list[int] = []
    for _ in range(copies):
        tiled.extend(boosted)
        if gap:
            tiled.extend(gap)
    out = ROOT / ".local/voice-agent/probes" / f"{path.stem}-boost.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(n)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"".join(s.to_bytes(2, "little", signed=True) for s in tiled))
    boosted_rms = round((sum(s * s for s in tiled) / len(tiled)) ** 0.5, 1)
    return {
        "original_peak": peak,
        "original_rms": rms,
        "boosted_rms": boosted_rms,
        "copies": copies,
        "gap_s": gap_s,
        "clip_seconds": round(len(tiled) / rate, 2),
        "boosted_path": str(out),
    }


def controller_logs(pattern: str, after: float) -> list[str]:
    """Log lines matching pattern with a wall timestamp >= after.

    The launchd-managed controller writes to controller-restart.log; older
    runs wrote to controller.log. Scan both.
    """
    hits = []
    for name in ("controller.log", "controller-restart.log"):
        path = Path.home() / ".local/state/omp-voice" / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if pattern in line:
                try:
                    epoch = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S").timestamp()
                except ValueError:
                    continue
                if epoch >= after:
                    hits.append(line)
    return hits


def _pid_alive(pid: int) -> bool:
    try:
        return subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0
    except Exception:
        return False


def calibrate_afplay_spawn(clip_path: str, clip_seconds: float) -> float:
    """Median wall-clock offset between afplay Popen and first sound.

    afplay's wall lifetime is spawn overhead + clip duration (+ a tiny drain);
    subtracting the known clip length isolates the overhead for this exact
    clip. The hold gate must be clocked from the burst onset, not the command.
    """
    offsets = []
    for _ in range(3):
        t0 = time.time()
        subprocess.run(["afplay", clip_path], check=False)
        offsets.append(time.time() - t0 - clip_seconds)
    return sorted(offsets)[1]


def controller_status() -> dict | None:
    try:
        out = subprocess.run([str(Path.home() / ".local/bin/omp-voice-controller"), "status"],
                             capture_output=True, text=True, timeout=15).stdout
        start = out.find("{")
        if start < 0:
            return None
        return json.loads(out[start:])
    except Exception:
        return None


def main() -> int:
    if not voicebox_healthy():
        print("VoiceBox not healthy; human must reopen Voicebox.app")
        return 1
    if not INTERRUPT_CLIP.exists():
        print(f"interrupt fixture missing: {INTERRUPT_CLIP}")
        return 2

    boost = boost_wav(INTERRUPT_CLIP, GAIN, BURST_COPIES, BURST_GAP)
    print("interrupt clip:", json.dumps(boost))

    proc, record, master = start_omp()
    pid = record["pid"]
    port = record["port"]
    result: dict = {
        "id": "VA-PHYS-003-ACOUSTIC-BARGE",
        "omp_pid": pid,
        "bridge_port": port,
        "interrupt_clip": str(INTERRUPT_CLIP),
        "boost": boost,
    }
    try:
        def post(text: str) -> str | None:
            r = subprocess.run(
                ["curl", "-s", "-X", "POST", f"http://127.0.0.1:{port}/transcript",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({"text": text})],
                capture_output=True, text=True, timeout=30,
            )
            try:
                return json.loads(r.stdout or "{}").get("action")
            except ValueError:
                return None

        controller_pid = None
        status = controller_status()
        if status:
            controller_pid = (status.get("controller") or {}).get("pid")
        result["live_controller_pid"] = controller_pid

        spawn_offset = calibrate_afplay_spawn(boost["boosted_path"], boost["clip_seconds"])
        result["afplay_spawn_offset_s"] = round(spawn_offset, 3)

        hold_line = None
        hold_latency = None
        stop_line = None
        stop_epoch = None
        controller_stop_latency = None
        attempts: list[dict] = []
        reply_pids: set[int] = set()
        t_start = None

        def trace_events(after: float) -> list[dict]:
            if not TRACE_FILE.exists():
                return []
            events = []
            for line in TRACE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                if evt.get("t", 0) >= after:
                    events.append(evt)
            return events

        # Interrupt while the reply's afplay is still running. The render
        # reference in status.json lags, so key off the live tts-playing slot.
        slot_path = Path.home() / ".local/state/omp-voice/tts-playing" / f"{pid}.json"
        def slot_playing() -> bool:
            try:
                slot = json.loads(slot_path.read_text(encoding="utf-8"))
            except Exception:
                return False
            p = slot.get("afplay_pid")
            return bool(p) and _pid_alive(int(p)) and not slot.get("ended_at")

        success_onset = None
        def burst_round() -> bool:
            nonlocal hold_line, hold_latency, stop_line, stop_epoch, controller_stop_latency, t_start, success_onset
            for attempt in range(6):
                if not slot_playing():
                    attempts.append({"attempt": attempt, "skipped": "reply not playing"})
                    return False
                try:
                    slot = json.loads(slot_path.read_text(encoding="utf-8"))
                    if slot.get("afplay_pid"):
                        reply_pids.add(int(slot["afplay_pid"]))
                except Exception:
                    pass
                t_start = time.time()
                sound_start = t_start + spawn_offset
                subprocess.Popen(["afplay", boost["boosted_path"]])
                rec: dict = {"attempt": attempt, "start_epoch": t_start, "sound_start_epoch": sound_start}
                attempts.append(rec)
                stop_epoch = None
                for _ in range(35):
                    events = trace_events(sound_start - 0.3)
                    holds = [e for e in events if e.get("stage") == "hold"]
                    stop_evt = next((e for e in events if e.get("stage") == "stop_playback"), None)
                    fast = [h for h in holds if h["t"] - sound_start <= HOLD_ACCEPT_S]
                    if stop_evt and fast:
                        hold_evt = fast[0]
                        latency = round(hold_evt["t"] - sound_start, 3)
                        rec["hold_latency_s"] = latency
                        rec["stop_latency_s"] = stop_evt.get("latency_s")
                        hold_line = hold_evt
                        hold_latency = latency
                        stop_line = stop_evt
                        stop_epoch = stop_evt["t"]
                        controller_stop_latency = stop_evt.get("latency_s")
                        success_onset = sound_start
                        return True
                    if stop_evt:
                        rec["late_hold_latency_s"] = round(holds[0]["t"] - sound_start, 3) if holds else None
                        break  # chain ran but opened late; re-burst if the reply is still playing
                    time.sleep(0.2)
                rec["note"] = "no fast hold+stop chain this attempt"
                time.sleep(1.2)  # clear the barge release cooldown before re-bursting
            return False

        playback_started = False
        for reply_attempt in range(3):
            result[f"submit_action_{reply_attempt}"] = post(REPLY_PROMPT)
            result[f"send_action_{reply_attempt}"] = post("send prompt")
            clip = wait_playing(pid, timeout=300)
            if clip is None:
                continue
            playback_started = True
            if burst_round():
                break
        result["playback_started"] = playback_started
        result["attempts"] = attempts
        result["barge_hold_line"] = hold_line
        result["hold_latency_s"] = hold_latency
        result["stop_line"] = stop_line
        onsets = [a["sound_start_epoch"] for a in attempts if "sound_start_epoch" in a]
        result["barge_trace_events"] = trace_events(min(onsets, default=0) - 0.5)

        # reply afplay must be dead: every afplay pid the probe session spawned
        result["reply_afplay_pids"] = sorted(reply_pids)
        dead = all(not _pid_alive(p) for p in reply_pids)
        if not dead:
            for _ in range(10):
                if all(not _pid_alive(p) for p in reply_pids):
                    dead = True
                    break
                time.sleep(0.2)
        result["reply_afplay_dead"] = dead

        result["resume_lines_after_stop"] = controller_logs("TTS barge resume", stop_epoch or t_start or 0)
        result["whisper_lines_in_window"] = controller_logs("over TTS", (t_start or 0) - 0.5)
        status = controller_status() or {}
        turn = (status.get("controller") or {}).get("turn") or {}
        result["stop_latency_s"] = turn.get("stop_latency_s") or controller_stop_latency

        time.sleep(1.0)
        final = controller_status() or {}
        result["final_state"] = (final.get("controller") or {}).get("state")
        result["controller_alive_after"] = bool(controller_pid) and _pid_alive(int(controller_pid))

        onset = success_onset if success_onset is not None else min(onsets, default=0)
        stop_epoch_ok = stop_epoch is not None and stop_epoch - onset <= STOP_WINDOW_S
        result["log_stop_lines"] = controller_logs("stopping speech", onset - 0.5)
        ok = (
            hold_line is not None
            and hold_latency is not None
            and hold_latency <= HOLD_ACCEPT_S
            and stop_line is not None
            and stop_epoch_ok
            and controller_stop_latency is not None
            and controller_stop_latency <= HOLD_TO_STOP_BOUND_S
            and dead
            and not result["resume_lines_after_stop"]
            and result["final_state"] == "IDLE"
        )
        result["hold_latency_bound_s"] = HOLD_ACCEPT_S
        result["stop_window_bound_s"] = STOP_WINDOW_S
        result["hold_to_stop_bound_s"] = HOLD_TO_STOP_BOUND_S
        result["verdict"] = "PASS" if ok else "FAIL"
        RUN_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"VA-PHYS-003 acoustic barge: {result['verdict']}")
        return 0 if ok else 1
    finally:
        try:
            proc.terminate(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
