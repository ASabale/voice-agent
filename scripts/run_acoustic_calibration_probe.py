#!/usr/bin/env python3
"""VA-CAL-001: measure the three acoustic estimators against real playback.

Idle sampling gives the ambient baseline. Then the root OMP session is asked
to speak a paragraph; every second of playback is sampled from status.json
plus the system output volume. The run JSON is the calibration evidence for
the adaptive duck depth (spec §3) — no invented constants.

Run: ~/.local/share/omp-voice/venv/bin/python scripts/run_acoustic_calibration_probe.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

STATUS = Path(os.path.expanduser("~/.local/state/omp-voice/status.json"))
RUNS = Path(__file__).resolve().parents[1] / ".local/voice-agent/runs"
RUNS.mkdir(parents=True, exist_ok=True)


def status() -> dict:
    try:
        return json.loads(STATUS.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def volume() -> int | None:
    try:
        out = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True, timeout=5,
        )
        return int(out.stdout.strip())
    except Exception:
        return None


def playing() -> bool:
    """True if any session has a live afplay clip (flat status.json has no such key)."""
    slots = Path(os.path.expanduser("~/.local/state/omp-voice/tts-playing"))
    for path in slots.glob("*.json"):
        try:
            slot = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        pid = slot.get("afplay_pid")
        if not pid or slot.get("ended_at"):
            continue
        try:
            if subprocess.run(["kill", "-0", str(pid)], capture_output=True).returncode == 0:
                return True
        except Exception:
            continue
    return False


def main() -> int:
    bridge = os.environ.get("VOICE_BRIDGE_PORT")
    if not bridge:
        sessions = Path(os.path.expanduser("~/.local/state/omp-voice/sessions"))
        for path in sessions.glob("*.json"):
            try:
                record = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(record.get("port"), int):
                bridge = str(record["port"])
                break
    if not bridge:
        print("no voice bridge registered; start an omp session first", file=sys.stderr)
        return 1

    rows: list[dict] = []
    def sample(tag: str) -> None:
        s = status()
        rows.append({
            "t": time.time(),
            "tag": tag,
            "state": s.get("state"),
            "ambient_rms": s.get("ambient_rms"),
            "ambient_long_rms": s.get("ambient_long_rms"),
            "ambient_confidence": s.get("ambient_confidence"),
            "echo_rms_full_gain": s.get("echo_rms_full_gain"),
            "echo_rms_current": s.get("echo_rms_current"),
            "near_end_rms": s.get("near_end_rms"),
            "aec_echo_db": s.get("aec_echo_db"),
            "aec_confidence": s.get("aec_confidence"),
            "volume": volume(),
        })

    print("[cal] idle baseline 20 s")
    for _ in range(20):
        sample("idle")
        time.sleep(1)

    subprocess.run(
        ["curl", "-s", "-m", "15", f"http://127.0.0.1:{bridge}/transcript",
         "-H", "Content-Type: application/json",
         "-d", json.dumps({"text": "Calibration: please read one paragraph about echo cancellation."})],
        timeout=30, check=False,
    )

    # Reply generation plus playback is slow on the single-slot local engine.
    print("[cal] waiting for playback to start")
    is_playing = False
    for _ in range(120):
        if playing():
            is_playing = True
            break
        time.sleep(1)
    if not is_playing:
        print("[cal] no playback detected; recording ambient only", file=sys.stderr)

    print("[cal] playback sampling 45 s")
    for _ in range(45):
        sample("playback" if is_playing else "post")
        time.sleep(1)

    for _ in range(15):
        sample("after")
        time.sleep(1)

    def agg(tag: str, key: str) -> dict:
        vals = [r[key] for r in rows if r["tag"] == tag and r[key] is not None]
        if not vals:
            return {}
        vals.sort()
        return {"min": round(vals[0], 1), "median": round(vals[len(vals) // 2], 1), "max": round(vals[-1], 1)}

    summary = {
        "idle_ambient": agg("idle", "ambient_rms"),
        "idle_confidence": agg("idle", "ambient_confidence"),
        "playback_echo_full_gain": agg("playback", "echo_rms_full_gain"),
        "playback_echo_current": agg("playback", "echo_rms_current"),
        "playback_ambient": agg("playback", "ambient_rms"),
        "playback_near_end": agg("playback", "near_end_rms"),
        "playback_volume": agg("playback", "volume"),
        "after_ambient": agg("after", "ambient_rms"),
        "after_echo": agg("after", "echo_rms_full_gain"),
    }
    out = RUNS / "VA-CAL-001-ACOUSTIC.json"
    out.write_text(json.dumps({"rows": rows, "summary": summary}, indent=1))
    print(json.dumps(summary, indent=1))
    print(f"[cal] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
