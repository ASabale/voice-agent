#!/usr/bin/env python3
"""VA-QUALITY-001 row E — human barge during an explanation.

Level 5 human-gated: the probe launches an isolated omp session, submits a
long explanation prompt, then WAITs for Akshay to say "hey jarvis stop"
(plain speech, no synthetic audio) over the live reply. The probe records the
sub-second trace chain (hold -> clip -> whisper -> stop_playback), the reply
afplay death, whether the cut text resumes, and whether a follow-up turn
still plays. The pass verdict is Akshay's, recorded verbatim; the probe only
supplies the measurements.

Run: ~/.local/share/omp-voice/venv/bin/python scripts/run_human_barge_probe.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_fixture_pipeline import (  # noqa: E402
    start_omp,
    wait_playing,
    voicebox_healthy,
)

ROOT = Path(__file__).resolve().parent.parent
RUN_FILE = ROOT / ".local/voice-agent/runs/VA-QUALITY-001-E-HUMAN-BARGE.json"
TRACE_FILE = Path.home() / ".local/state/omp-voice/barge-trace.jsonl"
LOG_FILE = Path.home() / ".local/state/omp-voice/controller-restart.log"
EXPLAIN_PROMPT = (
    "Explain how echo cancellation works in this voice stack, about 250 "
    "words, sentence by sentence."
)


def controller_pid() -> int | None:
    status = Path.home() / ".local/state/omp-voice/status.json"
    try:
        return int(json.loads(status.read_text())["controller"]["pid"])
    except Exception:
        return None


def trace_events(after: float) -> list[dict]:
    if not TRACE_FILE.exists():
        return []
    out = []
    for line in TRACE_FILE.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("t", 0) >= after:
            out.append(e)
    return out


def controller_state() -> str | None:
    out = subprocess.run(["/Users/<user>/.local/bin/omp-voice-controller", "status"],
                         capture_output=True, text=True, check=False).stdout
    i = out.find("{")
    if i < 0:
        return None
    try:
        return json.loads(out[i:])["controller"].get("state")
    except Exception:
        return None


def main() -> int:
    if not voicebox_healthy():
        print("VoiceBox not healthy; stop the run.", file=sys.stderr)
        return 1
    proc = record = master = None
    result: dict = {"started_at": datetime.now(timezone.utc).isoformat()}
    try:
        proc, record, master = start_omp()
        pid = proc.pid
        result["omp_pid"] = pid
        result["controller_pid"] = controller_pid()
        print(f"session pid {pid}; controller {result['controller_pid']}", flush=True)
        subprocess.run(["sleep", "1"], check=False)
        for text in (EXPLAIN_PROMPT, "send prompt"):
            r = subprocess.run(
                ["curl", "-s", "-X", "POST", f"http://127.0.0.1:{record['port']}/transcript",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({"text": text})],
                capture_output=True, text=True, check=False)
            result[f"send_{text[:6]}"] = r.stdout.strip()
        clip = wait_playing(pid, timeout=240)
        if clip is None:
            result["error"] = "reply never started playing"
            RUN_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
            return 1
        onset = time.time()
        result["reply_start_epoch"] = onset
        print("Reply is playing. Say 'hey jarvis stop' out loud now.", flush=True)
        # Wait up to 45 s for a hold+stop chain triggered by the human voice.
        stop_evt = None
        hold_evt = None
        for _ in range(225):
            events = trace_events(onset)
            stops = [e for e in events if e.get("stage") == "stop_playback" and "stop" in (e.get("text") or "").lower()]
            if stops:
                stop_evt = stops[0]
                holds = [e for e in events if e.get("stage") == "hold" and e["t"] <= stop_evt["t"]]
                hold_evt = holds[-1] if holds else None
                break
            time.sleep(0.2)
        result["hold_event"] = hold_evt
        result["stop_event"] = stop_evt
        if stop_evt and hold_evt:
            result["hold_to_stop_s"] = round(stop_evt["t"] - hold_evt["t"], 3)
        time.sleep(3.0)
        result["state_after_stop"] = controller_state()
        # Does a follow-up turn still play?
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", f"http://127.0.0.1:{record['port']}/transcript",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"text": "say exactly: follow-up confirmed"})],
            capture_output=True, text=True, check=False)
        subprocess.run(
            ["curl", "-s", "-X", "POST", f"http://127.0.0.1:{record['port']}/transcript",
             "-H", "Content-Type: application/json",
             "-d", json.dumps({"text": "send prompt"})],
            capture_output=True, text=True, check=False)
        follow = wait_playing(pid, timeout=120)
        result["followup_played"] = follow is not None
        result["trace_window"] = trace_events(onset)
        # Capture 15 s past the follow-up so late whisper transcripts land in the evidence.
        deadline = max(onset + 120, time.time() + 15)
        while time.time() < deadline:
            time.sleep(1)
        result["trace_tail"] = trace_events(onset)
        result["final_state"] = controller_state()
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                pass
        result["ended_at"] = datetime.now(timezone.utc).isoformat()
        RUN_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if master is not None:
            try:
                os.close(master)
            except OSError:
                pass
        print(json.dumps({k: result.get(k) for k in ("hold_event", "stop_event", "hold_to_stop_s", "state_after_stop", "followup_played")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
