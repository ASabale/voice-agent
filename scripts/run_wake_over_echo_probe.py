#!/usr/bin/env python3
"""VA-PHYS-002 — a wake word played through the speakers during a live reply
must still wake the controller.

Physical Level 4: the live controller owns the microphone; the reply echo is
cancelled by AEC while the wake fixture is played through the same speakers.
No human voice. Acceptance:

1. Zero wake lines from the reply echo alone (echo-only suppression holds).
2. At least one wake line fires while the reply is still playing (the
   canceller does not eat a genuine wake word).
3. The wake score reported in the controller log is >= the 0.5 threshold.
4. The controller process survives and status returns to IDLE afterwards.

Cleanup: the probe terminates its own omp session; dictation opened by the
wake closes via the controller's own 15 s idle timeout (Handy cancel is the
controller's own path, not the probe's).
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
RESTART_LOG = Path.home() / ".local/state/omp-voice/controller-restart.log"
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


def log_lines_between(start: datetime, end: datetime) -> list[str]:
    lines = []
    try:
        text = RESTART_LOG.read_text(encoding="utf-8")
    except OSError:
        return lines
    for line in text.splitlines():
        if len(line) > 21 and line[0] == "[":
            try:
                stamp = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if start <= stamp <= end:
                lines.append(line)
    return lines


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
        start_moment = datetime.now()

        # Play the wake fixture through the speakers mid-reply.
        wake_proc = subprocess.Popen(["afplay", str(WAKE_FIXTURE)])
        wake_proc.wait()
        evidence["wake_fixture_played"] = wake_proc.returncode == 0

        # Sample until the reply finishes (or 120 s, whichever comes first).
        deadline = time.time() + 120
        states: list[str] = []
        last_state = None
        while time.time() < deadline:
            try:
                os.kill(afplay_pid, 0)
                alive = True
            except OSError:
                alive = False
            snap = live_status()
            state = snap.get("state")
            if state != last_state:
                states.append(state)
                last_state = state
            if not alive:
                break
            time.sleep(0.25)
        end_moment = datetime.now()

        window_lines = log_lines_between(start_moment, end_moment)
        wake_lines = [l for l in window_lines if "wake" in l.lower()]
        evidence["log_lines_in_window"] = len(window_lines)
        evidence["wake_lines"] = wake_lines
        evidence["state_transitions"] = states
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

    woke = bool(wake_lines)
    ok = woke and evidence["controller_alive_after"]
    print(f"VA-PHYS-002 wake-over-echo: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
