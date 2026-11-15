#!/usr/bin/env python3
"""AEC-REAL-006 live: a physical reference failure during real playback.

An isolated omp session started by this script speaks through the real
speakers (real VoiceBox audio, real afplay) while the live controller that
owns the microphone tracks the render reference. Mid-playback the clip file
is truncated on disk, the crashed-writer / cleanup-race shape. Acceptance:
the live controller logs "render reference unavailable", its status reports
the reference gone, no wake fires on the uncancelled echo, the process
survives, and a later reply reconnects the reference and cancels again.

This script opens no microphone, signals no protected pid, and posts only
to the session it starts.
"""

from __future__ import annotations

import contextlib
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
RUN_ID = "AEC-REAL-006-LIVE"
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
    status_before_failure = live_status()
    controller_pid = status_before_failure.get("pid")
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
    }
    partial: Path | None = None
    try:
        first = post(
            port,
            "Reply with exactly three medium sentences about the render reference, "
            "about forty words in total. Send prompt.",
        )
        evidence["first_submit"] = first.get("action")
        playing = pipe.wait_playing(pid, 240)
        if not playing:
            evidence["playback_started"] = False
            print(json.dumps(evidence, indent=2))
            return 1
        evidence["playback_started"] = True
        wav_path = Path(playing["reference"]["wav"])
        frames = int(playing["reference"]["frames"])
        evidence["clip_frames"] = frames
        evidence["clip_seconds"] = round(frames / 24000, 2)
        evidence["afplay_pid"] = int(playing["afplay_pid"])
        # Grab the clip bytes immediately: the extension unlinks the wav when
        # afplay exits, so a late read can hit FileNotFoundError.
        try:
            raw = wav_path.read_bytes()
        except OSError as exc:
            evidence["playback_race"] = str(exc)
            print(json.dumps(evidence, indent=2))
            return 1

        time.sleep(2.0)
        try:
            os.kill(int(playing["afplay_pid"]), 0)
        except OSError:
            evidence["clip_ended_before_failure"] = True
            print(json.dumps(evidence, indent=2))
            return 1
        snapshot = live_status()
        evidence["before_failure"] = {
            "render_connected": snapshot.get("render_connected"),
            "aec_echo_db": snapshot.get("aec_echo_db"),
            "aec_blocks": snapshot.get("aec_blocks"),
            "mic_dropped": snapshot.get("mic_dropped"),
            "mic_invalid": snapshot.get("mic_invalid"),
            "state": snapshot.get("state"),
        }

        # The crashed-writer shape: the slot announces a new reference whose
        # file is only half written. The key changes, so the controller
        # re-reads and must refuse it. afplay keeps playing the original
        # file it already has open, so real echo continues while the
        # reference is dead. (Truncating the original in place is NOT a
        # failure here: the key does not change, so the loaded PCM stays.)
        partial = wav_path.with_suffix(".partial.wav")
        partial.write_bytes(raw[: 44 + frames * 2 // 2])
        slot_path = REAL_STATE / "tts-playing" / f"{pid}.json"
        slot = json.loads(slot_path.read_text(encoding="utf-8"))
        slot["reference"]["wav"] = str(partial)
        slot_path.write_text(json.dumps(slot), encoding="utf-8")
        failure_moment = datetime.now()
        evidence["failure"] = {
            "bytes_announced": frames * 2 + 44,
            "bytes_on_disk": 44 + frames * 2 // 2,
            "at_local": failure_moment.strftime("%Y-%m-%d %H:%M:%S"),
        }

        saw_disconnect = False
        disconnect_latency = None
        for i in range(30):
            snap = live_status()
            if snap.get("render_connected") is False:
                saw_disconnect = True
                disconnect_latency = round(i * 0.2, 2)
                break
            time.sleep(0.2)
        evidence["disconnect_observed"] = saw_disconnect
        evidence["disconnect_latency_s"] = disconnect_latency

        window_lines = log_lines_after(failure_moment - timedelta(seconds=1))
        evidence["render_log_lines"] = [
            line for line in window_lines if "render" in line.lower()
        ]
        evidence["wake_lines_in_window"] = [
            line for line in window_lines if "wake triggered" in line.lower()
        ]
        evidence["barge_lines_in_window"] = [
            line for line in window_lines
            if any(word in line.lower() for word in ("hold", "whisper", "not stop"))
        ]

        time.sleep(2.0)
        after = live_status()
        evidence["during_failure"] = {
            "render_connected": after.get("render_connected"),
            "state": after.get("state"),
            "mic_dropped": after.get("mic_dropped"),
            "mic_invalid": after.get("mic_invalid"),
        }

        second = post(port, "Reply with exactly: Reference recovered. Send prompt.")
        evidence["second_submit"] = second.get("action")
        first_wav = str(wav_path)
        # wait_playing alone is not enough: the slot still carries the first
        # clip until it ends. Require a slot whose reference.wav is the new
        # clip before sampling the reconnect.
        second_play = None
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                data = json.loads(slot_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = None
            if (
                isinstance(data, dict)
                and data.get("afplay_pid")
                and not data.get("ended_at")
                and (data.get("reference") or {}).get("wav")
                not in (first_wav, str(partial))
            ):
                second_play = data
                break
            time.sleep(0.25)
        evidence["second_playback"] = bool(second_play)
        if second_play:
            evidence["second_wav"] = Path(second_play["reference"]["wav"]).name
        reconnected = {}
        # Sample while the clip is still playing: the tail guard clears the
        # reference 0.6 s after afplay exits, and a one-sentence clip is gone
        # within a second.
        for _ in range(120):
            snap = live_status()
            if snap.get("render_connected") is True:
                reconnected = snap
                break
            time.sleep(0.25)
        evidence["after_reconnect"] = {
            "render_connected": reconnected.get("render_connected"),
            "aec_echo_db": reconnected.get("aec_echo_db"),
            "aec_blocks": reconnected.get("aec_blocks"),
        }
        controller_alive = True
        try:
            os.kill(controller_pid, 0)
        except OSError:
            controller_alive = False
        evidence["controller_alive"] = controller_alive
    finally:
        if partial is not None:
            with contextlib.suppress(OSError):
                partial.unlink()
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
        evidence.get("before_failure", {}).get("render_connected") is True
        and evidence.get("disconnect_observed")
        and any("render reference unavailable" in line.lower() for line in evidence.get("render_log_lines", []))
        and not evidence.get("wake_lines_in_window")
        and evidence.get("during_failure", {}).get("state") == "IDLE"
        and evidence.get("second_playback")
        and evidence.get("after_reconnect", {}).get("render_connected") is True
        and evidence.get("controller_alive")
    )
    print(f"AEC-REAL-006 live: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())