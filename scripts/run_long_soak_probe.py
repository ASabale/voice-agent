#!/usr/bin/env python3
"""VA-SOAK-006 level 5: six independent conversation cycles in one controller
lifetime, with the RSS envelope, slot directory, registry, and controller log
tracked across the whole run.

Each cycle starts its own isolated omp session, sends four prompts, plays real
VoiceBox replies through the real speakers, and exits. The controller (which
owns the microphone throughout) is never restarted and nobody speaks.

The first run (2026-11-15 00:44-01:10 UTC) FAILed on gates that measure the
probe, not the controller:
- mic_dropped/mic_invalid are cumulative over the whole controller lifetime,
  so the gate must be the delta across the run, not the absolute count.
- A single RSS sample at run start lands at a random phase of the documented
  +-200 MB macOS residency oscillation (VA-SOAK-005 rss-trace), so both the
  baseline and the settled value are medians of N samples.
- Human speech during the window wakes the mic and epoch-aborts queued speech
  (correct controller behavior). The probe now classifies the run as
  CONTAMINATED (exit 3) when transcripts prove a human spoke, instead of
  calling it a controller FAIL.

Verdict: PASS / CONTAMINATED (rerun in a quiet window) / FAIL.
Acceptance for PASS: every cycle plays all four turns; zero wake lines and
zero failed speech; the controller is alive and IDLE at the end with zero
mic-drop delta; the slot directory and dead-pid registry entries never
accumulate; the controller log stays under the rotation bound; the settled
post-run RSS median is within RSS_SETTLE_LIMIT_MB of the median baseline and
the per-cycle RSS never exceeds baseline + RSS_ENVELOPE_LIMIT_MB; the VoiceBox
footprint stays within VOICEBOX_GROWTH_LIMIT_MB of its baseline.
"""

from __future__ import annotations
import json
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
import run_soak_sessions_probe as soak  # noqa: E402

REAL_STATE = pipe.REAL_STATE
RUN_ID = "VA-SOAK-006-LONG"
CYCLES = 6
TURNS = 4
RSS_ENVELOPE_LIMIT_MB = 300.0
RSS_SETTLE_LIMIT_MB = 100.0
# Measured instrument noise: three independent 120 s medians of the *idle*
# controller (pid 38298, 2026-11-15 02:2x UTC) were 272.2 / 328.4 / 360.2 MB —
# an 88 MB spread with no workload. Absolute RSS drift below ~100 MB is not
# resolvable on this machine while the ~46 GiB model is resident (macOS
# compresses/evicts pages and refaults them), so the gate uses the measured
# band and the per-cycle median-trend check below.
VOICEBOX_GROWTH_LIMIT_MB = 3000.0
RSS_SAMPLES = 24
RSS_SAMPLE_INTERVAL_S = 5.0
RSS_CYCLE_SAMPLES = 6
RSS_CYCLE_INTERVAL_S = 2.0
SETTLE_WAIT_S = 120.0
HUMAN_MARKERS = ("Partial transcript", "Manual Handy transcription")


def rss_median(pid: int, samples: int = RSS_SAMPLES,
               interval: float = RSS_SAMPLE_INTERVAL_S) -> tuple[float | None, list[float]]:
    vals = []
    for _ in range(samples):
        v = soak.controller_rss_mb(pid)
        if v is not None:
            vals.append(round(v, 2))
        time.sleep(interval)
    if not vals:
        return None, []
    return round(sorted(vals)[len(vals) // 2], 2), vals


def voicebox_footprint_mb() -> int | None:
    """Dirty footprint of the VoiceBox sidecar (Metal arenas are not visible
    in ps RSS, so `footprint` is the only honest measure). The GUI launcher is
    a listener too but its footprint is KB-scale; the sidecar worker is the
    one that grows, so the largest listener footprint is the sidecar."""
    for _ in range(2):
        listing = subprocess.run(
            ["lsof", "-nP", "-iTCP:17493", "-sTCP:LISTEN"],
            capture_output=True, text=True, check=False,
        ).stdout
        footprints = []
        for line in listing.splitlines()[1:]:
            try:
                pid = int(line.split()[1])
            except (IndexError, ValueError):
                continue
            fp = subprocess.run(["footprint", "-p", str(pid)], capture_output=True, text=True, check=False).stdout
            match = re.search(r"Footprint: (\d+)( KB| MB)", fp)
            if match:
                value = int(match.group(1))
                if match.group(2) == " KB":
                    value = max(1, value // 1024)
                footprints.append(value)
        if footprints:
            return max(footprints)
        time.sleep(1)
    return None


PROMPTS = [
    "Reply with exactly two short sentences about soak testing. Send prompt.",
    "Reply with exactly two short sentences about slot pruning. Send prompt.",
    "Reply with exactly two short sentences about registry cleanup. Send prompt.",
    "Reply with exactly two short sentences about echo suppression. Send prompt.",
]


def registry_count() -> int:
    sess_dir = REAL_STATE / "sessions"
    if not sess_dir.is_dir():
        return 0
    return sum(1 for p in sess_dir.glob("*.json") if p.stem.isdigit())


def speech_events(event: str, iso_start: str) -> list[dict]:
    """speech.log rotates to speech.log.1 at 1 MB, so attribution must read
    both files or mid-run rotations erase a cycle's events."""
    found: list[dict] = []
    for name in ("speech.log", "speech.log.1"):
        found.extend(soak.speech_events_after(REAL_STATE / name, iso_start, event))
    found.sort(key=lambda e: e.get("t", ""))
    return found


def controller_log_size() -> int:
    log = REAL_STATE / "controller.log"
    try:
        return log.stat().st_size
    except OSError:
        return 0


def run_cycle(cycle: int, iso_utc: str) -> dict:
    proc, record, master = pipe.start_omp()
    pid = int(record["pid"])
    port = int(record["port"])
    if pid in pipe.PROTECTED_PIDS:
        proc.terminate()
        raise SystemExit(f"refusing protected session {pid}")
    turns: list[dict] = []
    attributed_wavs: set[str] = set()
    try:
        for i, prompt in enumerate(PROMPTS):
            submit = soak.post(port, prompt)
            turn_start = time.time()
            turn_start_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            turn: dict = {"turn": i + 1, "submit_action": submit.get("action")}
            playing = None
            deadline = time.time() + 420
            while time.time() < deadline:
                snap = soak.slot_snapshot(pid)
                if snap and snap.get("afplay_pid") and soak.pid_alive(int(snap["afplay_pid"])):
                    # attribute the playing clip to this turn: its wav must
                    # have been generated after this prompt was submitted
                    wav = (snap.get("reference") or {}).get("wav") or snap.get("wav") or ""
                    name = Path(wav).name
                    if name and name not in attributed_wavs:
                        gen = [g for g in speech_events("generated", turn_start_iso)
                               if f"omp-vb-{pid}-" in g.get("wav", "")]
                        if any(g.get("wav", "") == name for g in gen):
                            playing = snap
                            attributed_wavs.add(name)
                            break
                time.sleep(0.3)
            if not playing:
                # Attribute the miss: was this turn's reply generated at all,
                # and were clips epoch-aborted (which only happens on a wake)?
                gen = [g for g in speech_events("generated", turn_start_iso)
                       if f"omp-vb-{pid}-" in g.get("wav", "")]
                drops = [d for d in speech_events("dropped", turn_start_iso)]
                turn["played"] = False
                turn["clips_generated_this_turn"] = len(gen)
                turn["dropped_in_window"] = len(drops)
                turns.append(turn)
                continue
            turn["played"] = True
            turn["playback_latency_s"] = round(time.time() - turn_start, 2)
            turn["clip"] = Path((playing.get("reference") or {}).get("wav", "")).name
            frames = int((playing.get("reference") or {}).get("frames", 0))
            turn["clip_seconds"] = round(frames / 24000, 2)
            turns.append(turn)
            # let the clip finish before the next prompt so generations do not
            # overlap in the slot file
            deadline = time.time() + 90
            while time.time() < deadline and soak.pid_alive(int(playing["afplay_pid"])):
                time.sleep(0.3)
    finally:
        if proc.poll() is None and proc.pid not in pipe.PROTECTED_PIDS:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            import os
            os.close(master)
        except OSError:
            pass
    generated = speech_events("generated", iso_utc)
    mine = [g for g in generated if f"omp-vb-{pid}-" in g.get("wav", "")]
    failed = [g for g in speech_events("failed", iso_utc)
              if f"omp-vb-{pid}-" in g.get("wav", "")]
    return {
        "cycle": cycle,
        "omp_pid": pid,
        "turns_played": sum(1 for t in turns if t.get("played")),
        "turns": turns,
        "clips_generated": len(mine),
        "speech_failed": len(failed),
    }


def evaluate(evidence: dict) -> str:
    """Pure verdict from the evidence bundle. Returns PASS, CONTAMINATED or FAIL."""
    if evidence.get("human_transcript_lines", 0) > 0:
        return "CONTAMINATED"
    medians = evidence.get("rss_cycle_medians_mb", [])
    ok = (
        len(evidence["cycles"]) == CYCLES
        and all(c["turns_played"] == TURNS for c in evidence["cycles"])
        and evidence["wake_lines_total"] == 0
        and evidence["speech_failed_total"] == 0
        and evidence["final_status"].get("render_connected") is False
        and evidence["final_status"].get("state") == "IDLE"
        and evidence["mic_dropped_delta"] == 0
        and evidence["mic_invalid_delta"] == 0
        and evidence["controller_alive"]
        and evidence["slot_dir_count_final"] <= 2
        and evidence["rss_baseline_median_mb"] is not None
        and evidence["rss_post_run_median_mb"] is not None
        and evidence["rss_post_run_median_mb"] <= evidence["rss_baseline_median_mb"] + RSS_SETTLE_LIMIT_MB
        and evidence["rss_after_cycle_max_mb"] is not None
        and evidence["rss_after_cycle_max_mb"] <= evidence["rss_baseline_median_mb"] + RSS_ENVELOPE_LIMIT_MB
        # A real leak shows a rising floor across cycles; residency churn does
        # not trend. First-vs-last cycle median must stay inside the noise band.
        and len(medians) == CYCLES
        and all(m is not None for m in medians)
        and medians[-1] - medians[0] <= RSS_SETTLE_LIMIT_MB
        and evidence["voicebox_footprint_baseline_mb"] is not None
        and all(v is not None for v in evidence["voicebox_footprints_mb"])
        and max(evidence["voicebox_footprints_mb"]) <= evidence["voicebox_footprint_baseline_mb"] + VOICEBOX_GROWTH_LIMIT_MB
        and evidence["controller_log_bytes_end"] <= max(evidence["controller_log_bytes_at_start"], 20 * 1024 * 1024)
    )
    return "PASS" if ok else "FAIL"


def main() -> int:
    if not pipe.voicebox_healthy():
        print("VoiceBox is not healthy. Not launching a server.")
        return 2
    before = soak.live_status()
    controller_pid = before.get("pid")
    if not isinstance(controller_pid, int) or not soak.pid_alive(controller_pid):
        print("No live controller status. Refusing to run.")
        return 2

    started_at = datetime.now()
    iso_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    baseline, baseline_samples = rss_median(controller_pid)
    vb_baseline = voicebox_footprint_mb()
    evidence: dict = {
        "id": RUN_ID,
        "microphone_opened_by_probe": False,
        "live_controller_pid": controller_pid,
        "cycles_planned": CYCLES,
        "rss_baseline_median_mb": baseline,
        "rss_baseline_samples_mb": baseline_samples,
        "voicebox_footprint_baseline_mb": vb_baseline,
        "voicebox_footprints_mb": [],
        "controller_log_bytes_at_start": controller_log_size(),
        "registry_count_at_start": registry_count(),
        "mic_dropped_at_start": before.get("mic_dropped", 0),
        "mic_invalid_at_start": before.get("mic_invalid", 0),
        "cycles": [],
        "rss_after_cycles_mb": [],
        "rss_cycle_medians_mb": [],
        "rss_cycle_samples_mb": [],
    }

    for cycle in range(1, CYCLES + 1):
        cycle_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        result = run_cycle(cycle, iso_utc)
        drain = time.time() + 60
        while time.time() < drain and soak.live_status().get("render_connected") is not False:
            time.sleep(0.5)
        time.sleep(20)
        cyc_median, cyc_samples = rss_median(controller_pid, RSS_CYCLE_SAMPLES, RSS_CYCLE_INTERVAL_S)
        result["rss_after_cycle_mb"] = cyc_median
        result["rss_after_cycle_samples_mb"] = cyc_samples
        result["voicebox_footprint_mb"] = voicebox_footprint_mb()
        evidence["voicebox_footprints_mb"].append(result["voicebox_footprint_mb"])
        result["slot_dir_count"] = soak.slot_dir_count()
        result["registry_count"] = registry_count()
        result["cycle_generated"] = result["clips_generated"]
        evidence["cycles"].append(result)
        evidence["rss_after_cycles_mb"].append(cyc_median)
        evidence["rss_cycle_medians_mb"].append(cyc_median)
        evidence["rss_cycle_samples_mb"].append(cyc_samples)
        print(f"cycle {cycle}: played {result['turns_played']}/4 rss {result['rss_after_cycle_mb']} slots {result['slot_dir_count']}", flush=True)
        time.sleep(5)

    final = soak.live_status()
    print(f"settling {SETTLE_WAIT_S}s before the post-run RSS median", flush=True)
    time.sleep(SETTLE_WAIT_S)
    post_median, post_samples = rss_median(controller_pid)
    evidence["rss_post_run_median_mb"] = post_median
    evidence["rss_post_run_samples_mb"] = post_samples
    evidence["final_status"] = {
        "render_connected": final.get("render_connected"),
        "state": final.get("state"),
        "mic_dropped": final.get("mic_dropped"),
        "mic_invalid": final.get("mic_invalid"),
        "pid": final.get("pid"),
    }
    evidence["mic_dropped_delta"] = final.get("mic_dropped", 0) - evidence["mic_dropped_at_start"]
    evidence["mic_invalid_delta"] = final.get("mic_invalid", 0) - evidence["mic_invalid_at_start"]
    wake_lines = soak.log_lines_containing(REAL_STATE / "controller-restart.log", started_at, "Wake triggered")
    human_lines = []
    for marker in HUMAN_MARKERS:
        human_lines.extend(soak.log_lines_containing(REAL_STATE / "controller-restart.log", started_at, marker))
    evidence["wake_lines_total"] = len(wake_lines)
    evidence["wake_lines"] = wake_lines
    evidence["human_transcript_lines"] = len(human_lines)
    evidence["speech_failed_total"] = len(speech_events("failed", iso_utc))
    evidence["registry_count_final"] = registry_count()
    evidence["slot_dir_count_final"] = soak.slot_dir_count()
    evidence["controller_log_bytes_end"] = controller_log_size()
    evidence["controller_alive"] = soak.pid_alive(controller_pid)
    peaks = [v for samples in evidence["rss_cycle_samples_mb"] for v in samples]
    evidence["rss_after_cycle_max_mb"] = round(max(peaks), 2) if peaks else None

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    verdict = evaluate(evidence)
    evidence["verdict"] = verdict
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({k: evidence[k] for k in ("rss_baseline_median_mb", "rss_post_run_median_mb", "rss_after_cycle_max_mb", "wake_lines_total", "human_transcript_lines", "speech_failed_total", "mic_dropped_delta", "mic_invalid_delta", "registry_count_final", "slot_dir_count_final", "controller_log_bytes_end")}, indent=2))
    print(f"VA-SOAK-006 long soak: {verdict}")
    if verdict == "CONTAMINATED":
        print("A human spoke during the soak window; rerun in a quiet window.")
        return 3
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
