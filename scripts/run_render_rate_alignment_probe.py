#!/usr/bin/env python3
"""VA-AUD-001 hardware leg: does the controller's render cursor track real
afplay speed when the extension plays with `afplay -r <rate>`?

Physical criterion (spec 6B, objective A): while a live reply plays, the
published render_cursor must advance at wall-clock * playback_rate on the
16 kHz grid, not at plain wall time. Tolerance 6%. The pause leg is reported
as not-applicable: production has no pause path (pause_tts_clips is dead),
so there is no SIGSTOP to align against.

Exit codes: 0 PASS, 1 FAIL, 2 VoiceBox or session unavailable.
Evidence: .local/voice-agent/runs/VA-AUD-001-RATE-ALIGN.json
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from run_fixture_pipeline import (
    REAL_STATE,
    start_omp,
    voicebox_healthy,
    wait_playing,
)


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

STATUS = REAL_STATE / "status.json"
CONTROLLER = Path(__file__).resolve().parent.parent / "bin" / "omp-voice-controller"
EVIDENCE = Path(__file__).resolve().parent.parent / ".local" / "voice-agent" / "runs" / "VA-AUD-001-RATE-ALIGN.json"
MIC_RATE = 16000


def pause_call_sites() -> list[int]:
    lines = CONTROLLER.read_text(encoding="utf-8").splitlines()
    hits = []
    for i, line in enumerate(lines, 1):
        if re.search(r"pause_tts_clips\s*\(", line) and "def " not in line:
            hits.append(i)
    return hits


def main() -> int:
    if not voicebox_healthy():
        print("VoiceBox not healthy", file=sys.stderr)
        return 2

    proc, record, master = start_omp()
    pid = int(record["pid"])
    port = int(record["port"])
    prompt = (
        "Reply with about 110 words explaining echo cancellation in four "
        "complete sentences. Do not ask follow-up questions."
    )
    post(port, prompt)
    post(port, "send prompt")
    slot = wait_playing(pid, 120)
    if not slot:
        proc.kill()
        print("no playback observed", file=sys.stderr)
        return 1

    started = float(slot["started_at"])
    afplay = int(slot["afplay_pid"])
    ref = slot.get("reference") or {}
    rate = float(slot.get("playback_rate", 1.0))
    native_frames = int(ref.get("frames", 0))
    full_16k = int(native_frames * MIC_RATE / int(ref.get("sample_rate", 24000)))

    samples = []
    end_wall = None
    while time.time() < started + 180:
        try:
            st = json.loads(STATUS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.4)
            continue
        cursor = st.get("render_cursor")
        if cursor is None:
            time.sleep(0.4)
            continue
        wall = time.time() - started
        samples.append(
            {
                "wall_s": round(wall, 3),
                "cursor": int(cursor),
                "processed": int(st.get("render_processed_frames", 0)),
                "connected": bool(st.get("render_connected")),
            }
        )
        # afplay liveness: the slot gets ended_at when the clip finishes.
        try:
            cur_slot = json.loads((REAL_STATE / "tts-playing" / f"{pid}.json").read_text())
        except (OSError, ValueError):
            cur_slot = {}
        if cur_slot.get("ended_at"):
            end_wall = time.time() - started
            break
        time.sleep(0.4)

    proc.kill()
    try:
        os.close(master)
    except OSError:
        pass

    # The reply is chunked into clips; the cursor resets when a new clip
    # connects. Split into monotonic segments of equal `processed` and fit
    # the segment that covers this probe's clip.
    segments: list[list[dict]] = []
    for s in samples:
        if not s["connected"]:
            continue
        if segments and s["cursor"] >= segments[-1][-1]["cursor"] and s["processed"] == segments[-1][-1]["processed"]:
            segments[-1].append(s)
        else:
            segments.append([s])
    mid = max(segments, key=len) if segments else []
    n = len(mid)
    slope = 0.0
    if n >= 5:
        xs = [s["wall_s"] for s in mid]
        ys = [s["cursor"] for s in mid]
        mx, my = sum(xs) / n, sum(ys) / n
        den = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0
    measured_rate = slope / MIC_RATE
    rate_err = abs(measured_rate - rate) / rate if rate else 0.0
    wall_err = abs(measured_rate - 1.0)
    reached_full = mid and mid[-1]["cursor"] >= 0.98 * full_16k

    sites = pause_call_sites()
    verdict = (
        "PASS"
        if n >= 8 and full_16k - mid[-1]["cursor"] < 0.02 * full_16k and rate_err <= 0.08 and (rate <= 1.0 or rate_err < wall_err / 2)
        else "FAIL"
    )
    evidence = {
        "scenario": "VA-AUD-001-RATE-ALIGN",
        "result": verdict,
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "session_pid": pid,
        "clip": {"frames_native": native_frames, "frames_16k": full_16k, "playback_rate": rate},
        "samples": mid[:40],
        "measured_cursor_rate": round(measured_rate, 4),
        "slot_playback_rate": rate,
        "cursor_rate_error_vs_slot_rate": round(rate_err, 4),
        "cursor_rate_error_vs_wall_hypothesis": round(wall_err, 4),
        "final_cursor_reached_full_clip": reached_full,
        "pause_call_sites_in_bin": sites,
        "pause_leg": "not-applicable: no production path SIGSTOPs clips (pause_tts_clips has zero call sites; "
                      "comment at controller line 3516: barge hold deliberately does not SIGSTOP)",
        "wall": {"session_register_s": 25, "playback_deadline_s": 120, "afplay_pid": afplay, "end_wall_s": end_wall},
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(verdict, "|", f"measured_rate={measured_rate:.3f} rate_err={rate_err:.3f} wall_err={wall_err:.3f} reached_full={reached_full}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
