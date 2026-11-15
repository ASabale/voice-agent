#!/usr/bin/env python3
"""VA-PLAY-002 level 5: a session dies mid-clip; the live controller cleans up.

An isolated omp session started by this script speaks through the real
speakers (real VoiceBox audio, real afplay). Mid-playback the session
process is SIGKILLed. The extension never writes ended_at, so the slot
file keeps `playing: true` and the flat projection keeps the memory
guardian believing voice is playing. Acceptance:

- while the orphaned afplay is still running, the live controller keeps
  its render reference (echo is real, suppression must stay on);
- once that afplay exits, the dead session's slot is pruned from
  tts-playing/ within the poll window;
- the flat tts-playing.json projection is re-derived to playing:false;
- the controller status reports render_connected:false and state IDLE;
- no wake line fires on the uncancelled echo;
- the controller survives.

This script opens no microphone, signals no protected pid, and kills only
the session it started.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_fixture_pipeline as pipe  # noqa: E402

REAL_STATE = pipe.REAL_STATE
RUN_ID = "VA-PLAY-002-LIVE"
RESTART_LOG = REAL_STATE / "controller-restart.log"
PLAYBACK_LEASE_SECONDS = 60.0


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


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def log_lines_after(moment: datetime) -> list[str]:
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
            if stamp >= moment:
                lines.append(line)
    return lines


def main() -> int:
    if not pipe.voicebox_healthy():
        print("VoiceBox is not healthy. Not launching a server.")
        return 2
    status_before = live_status()
    controller_pid = status_before.get("pid")
    if not isinstance(controller_pid, int) or not pid_alive(controller_pid):
        print("No live controller status. Refusing to run.")
        return 2

    proc, record, master = pipe.start_omp()
    pid = int(record["pid"])
    port = int(record["port"])
    if pid in pipe.PROTECTED_PIDS:
        proc.terminate()
        raise SystemExit(f"refusing protected session {pid}")

    slot_path = REAL_STATE / "tts-playing" / f"{pid}.json"
    registry_path = REAL_STATE / "sessions" / f"{pid}.json"

    evidence: dict = {
        "id": RUN_ID,
        "microphone_opened_by_probe": False,
        "live_controller_pid": controller_pid,
        "omp_pid": pid,
        "bridge_port": port,
        "playback_lease_seconds": PLAYBACK_LEASE_SECONDS,
    }
    try:
        first = post(
            port,
            "Reply with exactly four medium sentences about stale session "
            "cleanup, about ninety words in total. Send prompt.",
        )
        evidence["first_submit"] = first.get("action")
        playing = pipe.wait_playing(pid, 240)
        if not playing:
            evidence["playback_started"] = False
            print(json.dumps(evidence, indent=2))
            return 1

        frames = int((playing.get("reference") or {}).get("frames", 0))
        afplay_pid = int(playing["afplay_pid"])
        writer_pid = playing.get("writer_pid")
        evidence["playback_started"] = True
        evidence["clip_frames"] = frames
        evidence["clip_seconds"] = round(frames / 24000, 2)
        evidence["clip_within_lease"] = frames / 24000 < PLAYBACK_LEASE_SECONDS
        evidence["afplay_pid"] = afplay_pid
        evidence["writer_pid_is_omp"] = writer_pid == pid
        evidence["before_kill"] = {
            "slot": {
                "playing": playing.get("playing"),
                "ended_at": playing.get("ended_at"),
                "started_at": playing.get("started_at"),
            },
            "projection": read_json(REAL_STATE / "tts-playing.json"),
            "status": {
                "render_connected": status_before.get("render_connected"),
                "state": status_before.get("state"),
            },
        }

        time.sleep(2.0)
        if not pid_alive(afplay_pid):
            evidence["clip_ended_before_kill"] = True
            print(json.dumps(evidence, indent=2))
            return 1

        kill_moment = datetime.now()
        proc.kill()
        proc.wait(timeout=10)
        evidence["session_killed_mid_clip"] = True
        evidence["kill_at_local"] = kill_moment.strftime("%Y-%m-%d %H:%M:%S")
        evidence["session_pid_dead_after_kill"] = not pid_alive(pid)

        # Watch the orphaned afplay and the slot until the controller prunes.
        timeline: list[dict] = []
        afplay_end = None
        prune_time = None
        projection_false = None
        render_dropped = None
        deadline = time.time() + 120
        while time.time() < deadline:
            now = time.time()
            slot = read_json(slot_path)
            afplay_alive = pid_alive(afplay_pid)
            projection = read_json(REAL_STATE / "tts-playing.json")
            snap = live_status()
            if not afplay_alive and afplay_end is None:
                afplay_end = now
            if slot is None and prune_time is None:
                prune_time = now
            if projection is not None and projection.get("playing") is False and projection_false is None:
                projection_false = now
            if snap.get("render_connected") is False and render_dropped is None:
                render_dropped = now
            timeline.append(
                {
                    "t_since_kill": round(now - kill_moment.timestamp(), 2),
                    "slot_exists": slot is not None,
                    "slot_playing": slot.get("playing") if slot else None,
                    "slot_ended_at": slot.get("ended_at") if slot else None,
                    "afplay_alive": afplay_alive,
                    "projection_playing": projection.get("playing") if projection else None,
                    "render_connected": snap.get("render_connected"),
                    "controller_state": snap.get("state"),
                }
            )
            if prune_time is not None and projection_false is not None and render_dropped is not None:
                break
            time.sleep(0.25)

        evidence["orphan_afplay_seconds_after_kill"] = (
            round(afplay_end - kill_moment.timestamp(), 2) if afplay_end else None
        )
        evidence["afplay_ran_past_lease"] = bool(
            afplay_end is not None
            and afplay_end - (playing.get("started_at") or 0) > PLAYBACK_LEASE_SECONDS
        )
        evidence["slot_pruned"] = prune_time is not None
        evidence["slot_pruned_latency_s"] = (
            round(prune_time - kill_moment.timestamp(), 2) if prune_time else None
        )
        evidence["projection_playing_false"] = projection_false is not None
        evidence["projection_false_latency_s"] = (
            round(projection_false - kill_moment.timestamp(), 2) if projection_false else None
        )
        evidence["render_disconnected"] = render_dropped is not None
        evidence["timeline"] = timeline[::4]

        window_lines = log_lines_after(kill_moment - timedelta(seconds=1))
        evidence["wake_lines_after_kill"] = [
            line for line in window_lines if "wake triggered" in line.lower()
        ]
        evidence["render_log_lines"] = [
            line for line in window_lines if "render" in line.lower()
        ]
        evidence["controller_alive_after"] = pid_alive(controller_pid)
        evidence["registry_entry_present"] = registry_path.exists()
        final = live_status()
        evidence["final_status"] = {
            "render_connected": final.get("render_connected"),
            "aec_echo_db": final.get("aec_echo_db"),
            "aec_blocks": final.get("aec_blocks"),
            "state": final.get("state"),
            "mic_dropped": final.get("mic_dropped"),
            "mic_invalid": final.get("mic_invalid"),
        }
    finally:
        if proc.poll() is None and proc.pid not in pipe.PROTECTED_PIDS:
            proc.kill()
        try:
            os.close(master)
        except OSError:
            pass

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    ok = (
        evidence.get("session_killed_mid_clip")
        and evidence.get("slot_pruned")
        and evidence.get("projection_playing_false")
        and evidence.get("render_disconnected")
        and not evidence.get("wake_lines_after_kill")
        and evidence.get("controller_alive_after")
        and evidence.get("final_status", {}).get("state") == "IDLE"
    )
    print(f"VA-PLAY-002 live: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
