#!/usr/bin/env python3
"""AEC-REAL-001 live: echo-only wake suppression across a full reply.

An isolated omp session speaks through the real speakers while the live
controller that owns the microphone cancels the echo. Akshay does not
speak. Acceptance: every status window during playback reports a
cancelled (negative dB) residual, zero wake lines fire, and the process
survives. The controller cannot be restarted by the loop, so the guard
counter added in this iteration is not yet observable live; the raw
window is recorded as-is.

Opens no microphone, signals no protected pid, posts only to the session
it starts.
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
RUN_ID = "AEC-REAL-001-LIVE"
RESTART_LOG = Path.home() / ".local" / "state" / "omp-voice" / "controller-restart.log"


def post(port: int, text: str) -> dict:
    if port == 62283:
        raise SystemExit("refusing the user's bridge")
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
        print("VoiceBox is not healthy. Not launching a server.")
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
        "controller_is_pre_existing": True,
        "omp_pid": pid,
        "bridge_port": port,
        "note": "guard counter (aec_guard_blocks) is published by the "
        "pre-existing controller; windows record aec_echo_db and guard blocks",
    }
    try:
        submit = post(
            port,
            "Reply with exactly four medium sentences about echo cancellation, "
            "about ninety words in total. Send prompt.",
        )
        evidence["submit_action"] = submit.get("action")
        playing = pipe.wait_playing(pid, 240)
        if not playing:
            evidence["playback_started"] = False
            print(json.dumps(evidence, indent=2))
            return 1
        evidence["playback_started"] = True
        evidence["clip_frames"] = int(playing["reference"]["frames"])
        evidence["clip_seconds"] = round(int(playing["reference"]["frames"]) / 24000, 2)
        afplay_pid = int(playing["afplay_pid"])
        start_moment = datetime.now()

        windows: list[dict] = []
        last_seen = None
        while True:
            try:
                os.kill(afplay_pid, 0)
                os_alive = True
            except OSError:
                os_alive = False
            snap = live_status()
            fields = {
                "at_local": datetime.now().strftime("%H:%M:%S"),
                "render_connected": snap.get("render_connected"),
                "aec_echo_db": snap.get("aec_echo_db"),
                "aec_blocks": snap.get("aec_blocks"),
                "aec_guard_blocks": snap.get("aec_guard_blocks"),
                "render_cursor": snap.get("render_cursor"),
                "state": snap.get("state"),
            }
            key = (fields["aec_echo_db"], fields["aec_blocks"])
            if fields["aec_blocks"] and key != last_seen:
                windows.append(fields)
                last_seen = key
            if not os_alive:
                break
            time.sleep(0.25)
        end_moment = datetime.now()

        evidence["windows_during_playback"] = windows
        if windows:
            dbs = [w["aec_echo_db"] for w in windows if w["aec_echo_db"] is not None]
            evidence["echo_db_min"] = min(dbs) if dbs else None
            evidence["echo_db_max"] = max(dbs) if dbs else None
            evidence["echo_db_median"] = sorted(dbs)[len(dbs) // 2] if dbs else None
        window_lines = log_lines_between(start_moment, end_moment)
        evidence["wake_lines_during_playback"] = [
            line for line in window_lines if "wake triggered" in line.lower()
        ]
        evidence["barge_hold_lines_during_playback"] = [
            line for line in window_lines
            if any(word in line.lower() for word in ("hold", "whisper"))
        ]
        evidence["controller_alive_after"] = live_status().get("pid") == controller_pid
    finally:
        if proc.poll() is None and proc.pid not in pipe.PROTECTED_PIDS:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    ok = (
        evidence.get("playback_started")
        and len(evidence.get("windows_during_playback", [])) >= 4
        and (evidence.get("echo_db_max") or 0) < 0.0
        and not evidence.get("wake_lines_during_playback")
        and evidence.get("controller_alive_after")
    )
    print(f"AEC-REAL-001 echo-only live: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
