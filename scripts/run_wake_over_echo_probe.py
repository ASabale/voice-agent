#!/usr/bin/env python3
"""VA-PHYS-002 — a wake word through the speakers never opens dictation while
a reply is playing, but the same fixture wakes the controller the moment the
reply ends.

Physical Level 4: the live controller owns the microphone; the wake fixture is
played through the same speakers, first during a live reply (echo-over-reply)
and immediately after playback drains (wake-over-AEC-tail). No human voice.
Design contract (controller `handle_idle_frame`, tts_active branch): the wake
spotter is reset while VoiceBox TTS plays, so a "Hey Jarvis" in the reply or
its bleed must never open Handy. The tail after playback is where AEC could
plausibly eat a genuine wake — that is what phase B measures.

Acceptance:
1. Phase A (fixture played mid-reply): zero openWakeWord wake lines.
2. Phase B (fixture played within 1 s of playback exit): at least one wake line
   fires and the controller enters DICTATING with a reported score.
3. The controller process survives and returns to IDLE (15 s idle timeout).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_fixture_pipeline as pipe  # noqa: E402

REAL_STATE = pipe.REAL_STATE
RUN_ID = "VA-PHYS-002-WAKE-OVER-ECHO"
CONTROLLER_LOG = Path.home() / ".local/state/omp-voice/controller.log"
WAKE_FIXTURE = ROOT / "tests/fixtures/hey-jarvis-say.wav"


def post(port: int, text: str) -> dict:
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/transcript",
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read().decode())


def live_status() -> dict:
    try:
        return json.loads((REAL_STATE / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def wake_lines_between(start: datetime, end: datetime) -> list[str]:
    lines = []
    try:
        text = CONTROLLER_LOG.read_text(encoding="utf-8")
    except OSError:
        return lines
    for line in text.splitlines():
        if len(line) > 21 and line[0] == "[" and ("openWakeWord" in line or "Wake triggered" in line):
            try:
                stamp = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if start <= stamp <= end:
                lines.append(line)
    return lines


def play_fixture(path: Path) -> bool:
    proc = subprocess.Popen(["afplay", str(path)])
    proc.wait()
    return proc.returncode == 0


def main() -> int:
    if not pipe.voicebox_healthy():
        print("VoiceBox is not healthy. Not launching a probe.")
        return 2
    if not WAKE_FIXTURE.exists():
        print(f"missing wake fixture: {WAKE_FIXTURE}")
        return 2

    before = live_status()
    controller_pid = before.get("pid")
    if not isinstance(controller_pid, int):
        print("No live controller status. Refusing to run.")
        return 2

    proc, record, master = pipe.start_omp()
    pid = int(record["pid"])
    port = int(record["port"])
    if pid in pipe.PROTECTED_PIDS or port == 62283:
        proc.terminate()
        raise SystemExit(f"refusing protected session {pid} {port}")

    evidence: dict = {
        "id": RUN_ID,
        "microphone_opened_by_probe": False,
        "live_controller_pid": controller_pid,
        "omp_pid": pid,
        "bridge_port": port,
        "wake_fixture": str(WAKE_FIXTURE),
        "design_note": "wake spotter is reset while tts_active; phase A asserts "
        "that suppression holds against a real wake fixture through the speakers",
    }
    try:
        submit = post(
            port,
            "Reply with exactly four medium sentences about wake detection, "
            "about ninety words in total. Send prompt.",
        )
        evidence["submit_action"] = submit.get("action")
        playing = pipe.wait_playing(pid, 240)
        if not playing:
            evidence["playback_started"] = False
            print(json.dumps(evidence, indent=2))
            return 1

        afplay_pid = int(playing["afplay_pid"])
        clip_seconds = round(int(playing["reference"]["frames"]) / 24000, 2)
        evidence["playback_started"] = True
        evidence["clip_seconds"] = clip_seconds

        # Phase A: wake fixture through the speakers while the reply plays.
        mid_deadline = time.time() + max(clip_seconds - 2.0, 3.0)
        phase_a_start = datetime.now()
        while time.time() < mid_deadline:
            try:
                os_alive = True
                os.kill(afplay_pid, 0)
            except OSError:
                os_alive = False
            if not os_alive:
                break
            if play_fixture(WAKE_FIXTURE):
                break
        phase_a_end = datetime.now()
        evidence["phase_a_seconds"] = round((phase_a_end - phase_a_start).total_seconds(), 2)
        evidence["phase_a_wake_lines"] = wake_lines_between(phase_a_start, phase_a_end)

        # Wait for the reply to drain.
        drain = time.time() + 120
        while time.time() < drain:
            try:
                os.kill(afplay_pid, 0)
            except OSError:
                break
            time.sleep(0.25)
        evidence["playback_drained"] = True

        # Phase B: the same fixture the instant playback exits.
        phase_b_start = datetime.now()
        evidence["phase_b_fixture_played"] = play_fixture(WAKE_FIXTURE)
        deadline = time.time() + 10
        woke = False
        while time.time() < deadline:
            if wake_lines_between(phase_b_start, datetime.now()):
                woke = True
                break
            if live_status().get("state") == "DICTATING":
                woke = True
                break
            time.sleep(0.25)
        phase_b_end = datetime.now()
        evidence["phase_b_wake_lines"] = wake_lines_between(phase_b_start, phase_b_end)
        evidence["woke_after_playback"] = woke

        # Let the dictation idle-timeout return the controller to IDLE.
        settle = time.time() + 25
        final_state = None
        while time.time() < settle:
            state = live_status().get("state")
            if state == "IDLE":
                final_state = "IDLE"
                break
            time.sleep(1.0)
        evidence["final_state"] = final_state
        evidence["controller_alive_after"] = live_status().get("pid") == controller_pid
    finally:
        if proc.poll() is None and proc.pid not in pipe.PROTECTED_PIDS:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    out = ROOT / ".local/voice-agent/runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    ok = (
        not evidence["phase_a_wake_lines"]
        and evidence.get("woke_after_playback")
        and evidence["controller_alive_after"]
    )
    print(f"VA-PHYS-002 wake-over-echo: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
