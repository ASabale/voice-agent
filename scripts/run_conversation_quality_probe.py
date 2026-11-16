#!/usr/bin/env python3
"""VA-QUALITY-001 — §5 conversational-quality matrix, automatable rows.

Runs one isolated omp session through scripted turns and measures what was
actually spoken (speech.log lines with OMP_VOICE_LOG_TEXT=1, filtered to the
probe session's clip prefix). Subjective rows (naturalness, helpfulness) and
physical rows (Scenario E barge with human voice, Scenario G eyes-off use)
are NOT auto-passed; the probe only emits the measurable proxies and marks
those rows NEEDS_HUMAN_APPROVAL.

Acceptance per scenario:
A  progress communication   2-6 short spoken updates; no raw command output
B  technical explanation     spoken text names failure, cause, action, outcome
C  complex explanation       <=200 spoken words, contains a definition marker
D  context retention         corrected value restated; original value recalled
F  uncertainty honesty        admits uncertainty; no invented date
H  slop scan                 zero hits on the filler list (reported, not gated)

Scenarios E and G require the owner's voice/attention and are recorded as
NEEDS_HUMAN_APPROVAL with the exact procedure.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_fixture_pipeline as pipe  # noqa: E402

REAL_STATE = pipe.REAL_STATE
RUN_ID = "VA-QUALITY-001-CONVERSATION-MATRIX"
SLOP = [
    "great question", "absolutely!", "certainly!", "i'm happy to", "i'd be happy",
    "delve", "in today's world", "it's important to note", "keep in mind",
    "as an ai", "let's dive in", "i hope this helps",
]
SPEECH = REAL_STATE / "speech.log"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


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


def spoken_lines(pid: int, start_iso: str, end_iso: str) -> list[dict]:
    """Generated speech lines for this probe session within [start, end]."""
    out = []
    try:
        text = SPEECH.read_text(encoding="utf-8")
    except OSError:
        return out
    for raw in text.splitlines():
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if rec.get("event") != "generated":
            continue
        if f"omp-vb-{pid}-" not in rec.get("wav", ""):
            continue
        if rec.get("t", "") < start_iso or rec.get("t", "") > end_iso:
            continue
        out.append(rec)
    return out


def words_of(line: dict) -> int:
    return len(line.get("text", "").split())


def wait_drain(pid: int, timeout: float) -> None:
    """Return once this session has no live afplay for 6 consecutive seconds
    (chunk gaps are < 6 s; a silent turn drains too)."""
    slot = REAL_STATE / "tts-playing" / f"{pid}.json"
    deadline = time.time() + timeout
    quiet = 0.0
    while time.time() < deadline:
        playing = False
        try:
            data = json.loads(slot.read_text(encoding="utf-8"))
            if data.get("afplay_pid") and not data.get("ended_at"):
                playing = True
        except (OSError, ValueError):
            playing = False
        if playing:
            quiet = 0.0
        else:
            quiet += 0.5
            if quiet >= 6.0:
                return
        time.sleep(0.5)


def main() -> int:
    if not pipe.voicebox_healthy():
        print("VoiceBox is not healthy. Not launching the probe.")
        return 2

    env = dict(os.environ)
    env["OMP_VOICE_LOG_TEXT"] = "1"
    master, slave = __import__("pty").openpty()
    proc = subprocess.Popen(
        ["omp"], stdin=slave, stdout=slave, stderr=slave,
        start_new_session=True, cwd="/Users/akshay/Development", env=env,
    )
    os.close(slave)
    begun = time.time()
    record = None
    while time.time() - begun < 25:
        record = pipe.newest_session(begun)
        if record and record.get("pid") == proc.pid:
            break
    if not record:
        proc.terminate()
        print("isolated omp session did not register")
        return 2
    pid, port = int(record["pid"]), int(record["port"])
    if pid in pipe.PROTECTED_PIDS or port == 62283:
        proc.terminate()
        raise SystemExit(f"refusing protected session {pid} {port}")

    turns: list[dict] = []

    def run_turn(scenario: str, prompt: str, wait: float = 180.0) -> list[dict]:
        start = now_iso()
        post(port, prompt)
        wait_drain(pid, wait)
        end = now_iso()
        lines = spoken_lines(pid, start, end)
        turns.append({"scenario": scenario, "prompt": prompt, "spoken": lines})
        print(f"{scenario}: {len(lines)} clips, {sum(map(words_of, lines))} words", flush=True)
        return lines

    try:
        a = run_turn(
            "A",
            "Create /tmp/quality-demo with three files: a.csv (three data rows), "
            "b.md (one heading and two bullets), c.json (valid JSON). Verify each "
            "file with a real command. Give one short spoken progress update per "
            "step - never read raw command output aloud. End by saying what "
            "succeeded and what failed.",
            wait=300,
        )
        b = run_turn(
            "B",
            "Run `cat /tmp/definitely-missing-42` so it fails. Then explain in "
            "spoken language, for a non-programmer: what failed, the most likely "
            "reason, what you do next, and whether the workaround succeeded.",
        )
        c = run_turn(
            "C",
            "Explain out loud, for someone new to audio engineering, how echo "
            "cancellation lets this voice system ignore its own speech. Define "
            "every technical term in the same sentence you introduce it. Stay "
            "under 150 spoken words.",
        )
        run_turn("D1", "Remember this decision for our session: the soak RSS "
                      "settle band is 100 MB. Say the value back.")
        d2 = run_turn("D2", "Correction: the settle band should be 150 MB. State "
                            "the current decision out loud.")
        d3 = run_turn("D3", "What was the original value before that correction?")
        f = run_turn(
            "F",
            "When exactly is VoiceBox 2.0 releasing? If you cannot verify it, "
            "say you do not know instead of guessing.",
        )

        all_text = " ".join(l.get("text", "") for t in turns for l in t["spoken"]).lower()
        evidence = {
            "id": RUN_ID,
            "omp_pid": pid,
            "bridge_port": port,
            "started_at": now_iso(),
            "turns": [{
                "scenario": t["scenario"],
                "clips": len(t["spoken"]),
                "words": sum(words_of(l) for l in t["spoken"]),
                "max_clip_words": max((words_of(l) for l in t["spoken"]), default=0),
                "texts": [l.get("text", "") for l in t["spoken"]],
            } for t in turns],
            "checks": {
                "A_progress_updates": 2 <= len(a) <= 6 and max(words_of(l) for l in a) <= 60
                and not any(re.search(r"\[|,|\{", l.get("text", "")) and words_of(l) > 30 for l in a),
                "B_failure_explanation": bool(re.search(r"fail|error|missing", all_text))
                and bool(re.search(r"because|reason|not exist|not found", all_text))
                and bool(re.search(r"instead|retry|create|fallback|skip|check", all_text))
                and bool(re.search(r"success|worked|succeeded|failed", all_text)),
                "C_concise_explanation": sum(words_of(l) for l in c) <= 200
                and bool(re.search(r"means|in other words|think of|like a", " ".join(l.get("text", "") for l in c).lower())),
                "D_context_retention": any("150" in l.get("text", "") for l in d2)
                and any("100" in l.get("text", "") for l in d3),
                "F_honesty": bool(re.search(r"don'?t know|do not know|no verified|unclear|cannot verify|not sure|unknown", " ".join(l.get("text", "") for l in f).lower()))
                and not re.search(r"\b(202[0-9]|january|february|march|april|may|june|july|august|september|october|november|december)\b", " ".join(l.get("text", "") for l in f).lower()),
                "H_slop_hits": {p: all_text.count(p) for p in SLOP if p in all_text},
            },
            "needs_human_approval": {
                "E_interruption": "Owner barges in with real voice during a long spoken explanation; acceptance: stop within 1.2 s, correct resume behavior, response addresses the interruption. Automated proxies exist (barge hold log, stop_latency_s) but the naturalness of recovery is a human judgment.",
                "G_screenless": "Owner completes a real task eyes-off for 10 minutes; acceptance: every outcome understood from speech alone. Entirely subjective; record the owner's verdict verbatim.",
            },
        }
        auto = [k for k in ("A_progress_updates", "B_failure_explanation", "C_concise_explanation", "D_context_retention", "F_honesty")]
        evidence["auto_verdict"] = "PASS" if all(evidence["checks"][k] for k in auto) else "FAIL"
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
    print(json.dumps({"checks": evidence["checks"], "auto_verdict": evidence["auto_verdict"]}, indent=2))
    return 0 if evidence["auto_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
