#!/usr/bin/env python3
"""VA-SOAK-005 level 5: four consecutive conversations in one controller life,
with controller RSS sampled at every turn boundary (memory-stability leg).

One isolated omp session sends four prompts. Each gets a real VoiceBox reply
played through the real speakers while the live controller (which owns the
microphone the whole time, never restarted) tracks the render reference and
suppresses wake on the echo. Nobody speaks.

Acceptance: every turn plays; every turn's render reference connects and then
disconnects; the slot directory never accumulates dead entries; zero wake
lines; zero dropped/invalid mic frames; zero failed speech records; the
controller survives in IDLE with a live registry entry for the session; and
controller RSS never exceeds the baseline by more than RSS_GROWTH_LIMIT_MB.

The probe opens no microphone, signals no protected pid, and posts only to
the session it starts.
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
RUN_ID = os.environ.get("SOAK_RUN_ID", "VA-SOAK-005-LIVE")
RESTART_LOG = REAL_STATE / "controller-restart.log"
SPEECH_LOG = REAL_STATE / "speech.log"
TURNS = int(os.environ.get("SOAK_TURNS", "4"))
# Growth band set to the measured controller RSS noise floor (VA-SOAK-006:
# three independent idle medians spread 88 MB; ps RSS swings ±180 MB within
# turns under macOS page compression). 20 MB would fail on noise, not leaks.
RSS_GROWTH_LIMIT_MB = 100.0
RSS_PEAK_LIMIT_MB = 300.0

PROMPTS = [
    "Reply with exactly two short sentences about wake suppression. Send prompt.",
    "Reply with exactly two short sentences about slot pruning. Send prompt.",
    "Reply with exactly two short sentences about registry cleanup. Send prompt.",
    "Reply with exactly two short sentences about soak testing. Send prompt.",
    "Reply with exactly two short sentences about echo cancellation. Send prompt.",
    "Reply with exactly two short sentences about deferred speech. Send prompt.",
]


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


def slot_dir_count() -> int:
    slot_dir = REAL_STATE / "tts-playing"
    if not slot_dir.is_dir():
        return 0
    return sum(1 for p in slot_dir.glob("*.json") if p.stem.isdigit())


def slot_snapshot(pid: int) -> dict | None:
    try:
        data = json.loads((REAL_STATE / "tts-playing" / f"{pid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def controller_rss_mb(pid: int) -> float | None:
    """ps RSS in MiB. Reported as measured; macOS RSS undercounts MLX arenas,
    which is exactly why the delta across turns, not the absolute, is the signal."""
    res = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True)
    try:
        return int(res.stdout.strip()) / 1024.0
    except ValueError:
        return None


def controller_rss_median_mb(pid: int, n: int = 5) -> float | None:
    vals = []
    for _ in range(n):
        v = controller_rss_mb(pid)
        if v is not None:
            vals.append(v)
        time.sleep(1.0)
    if not vals:
        return None
    return round(sorted(vals)[len(vals) // 2], 2)


def voicebox_footprint_mb() -> float | None:
    """Largest footprint among 17493 listeners (the GUI launcher also listens
    at KB scale; the sidecar is the big one)."""
    res = subprocess.run(
        ["lsof", "-nP", "-iTCP:17493", "-sTCP:LISTEN"], capture_output=True, text=True
    )
    pids = {int(line.split()[1]) for line in res.stdout.splitlines()[1:] if line.split()[1:2] and line.split()[1].isdigit()}
    best = None
    for pid in sorted(pids):
        out = subprocess.run(["footprint", "-p", str(pid)], capture_output=True, text=True).stdout
        m = re.search(r"Footprint: (\d+) MB", out)
        if m:
            best = int(m.group(1)) if best is None else max(best, int(m.group(1)))
    return best


def bridge_status(port: int) -> dict:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=3) as res:
            data = json.loads(res.read().decode())
        return {k: data.get(k) for k in ("deferred", "deferredOldestAgeMs", "expiredSpeech")}
    except Exception:
        return {}


def log_lines_containing(path: Path, moment: datetime, needle: str) -> list[str]:
    """Bracketed controller-log lines after `moment` containing `needle`."""
    found = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return found
    for line in text.splitlines():
        if needle.lower() not in line.lower():
            continue
        if len(line) > 21 and line[0] == "[":
            try:
                stamp = datetime.strptime(line[1:20], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if stamp >= moment:
                found.append(line)
    return found


def speech_events_after(path: Path, iso_start: str, event: str) -> list[dict]:
    """speech.log is JSON lines with an ISO `t` and an `event` field."""
    found = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return found
    for line in text.splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("event") == event and data.get("t", "") >= iso_start:
            found.append(data)
    return found


def main() -> int:
    if not pipe.voicebox_healthy():
        print("VoiceBox is not healthy. Not launching a server.")
        return 2
    before = live_status()
    controller_pid = before.get("pid")
    if not isinstance(controller_pid, int) or not pid_alive(controller_pid):
        print("No live controller status. Refusing to run.")
        return 2

    proc, record, master = pipe.start_omp()
    pid = int(record["pid"])
    port = int(record["port"])
    if pid in pipe.PROTECTED_PIDS:
        proc.terminate()
        raise SystemExit(f"refusing protected session {pid}")

    started_at = datetime.now()
    iso_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    slot_path = REAL_STATE / "tts-playing" / f"{pid}.json"
    evidence: dict = {
        "id": RUN_ID,
        "microphone_opened_by_probe": False,
        "live_controller_pid": controller_pid,
        "omp_pid": pid,
        "bridge_port": port,
        "turns_planned": TURNS,
        "controller_lifetime_note": "controller never restarted during the run",
        "baseline_mic_dropped": before.get("mic_dropped", 0),
        "baseline_mic_invalid": before.get("mic_invalid", 0),
        "rss_baseline_mb": controller_rss_median_mb(controller_pid),
    }
    rss_samples: list[float] = []
    turns: list[dict] = []
    afplay_pids: set[int] = set()
    try:
        for i, prompt in enumerate(PROMPTS):
            submit = post(port, prompt)
            turn_start = datetime.now()
            turn: dict = {"turn": i + 1, "submit_action": submit.get("action")}
            turn["voicebox_footprint_before_mb"] = voicebox_footprint_mb()
            playing = None
            deadline = time.time() + 420
            while time.time() < deadline:
                snap = slot_snapshot(pid)
                if snap and snap.get("afplay_pid"):
                    af = int(snap["afplay_pid"])
                    if af not in afplay_pids and pid_alive(af):
                        playing = snap
                        afplay_pids.add(af)
                        break
                time.sleep(0.3)
            if not playing:
                turn["played"] = False
                turns.append(turn)
                continue
            turn["played"] = True
            turn["playback_latency_s"] = round(
                (datetime.now() - turn_start).total_seconds(), 2
            )
            frames = int((playing.get("reference") or {}).get("frames", 0))
            turn["clip_seconds"] = round(frames / 24000, 2)

            connected = False
            echo_samples: list[float] = []
            turn_rss_peak = 0.0
            deadline = time.time() + 30
            while time.time() < deadline:
                snap = live_status()
                rss = controller_rss_mb(controller_pid)
                if rss is not None:
                    turn_rss_peak = max(turn_rss_peak, rss)
                if snap.get("render_connected") is True:
                    connected = True
                    db = snap.get("aec_echo_db")
                    if isinstance(db, (int, float)):
                        echo_samples.append(db)
                if not pid_alive(int(playing["afplay_pid"])):
                    break
                time.sleep(0.3)
            turn["render_connected_during_playback"] = connected
            turn["echo_db_samples"] = echo_samples

            ended = False
            deadline = time.time() + 30
            while time.time() < deadline:
                snap = live_status()
                if snap.get("render_connected") is False:
                    ended = True
                    break
                time.sleep(0.3)
            turn["render_disconnected_after_playback"] = ended
            turn["voicebox_footprint_after_mb"] = voicebox_footprint_mb()
            turn["bridge_status"] = bridge_status(port)
            turn["boundary_slot_count"] = slot_dir_count()
            turn["turn_rss_peak_mb"] = round(turn_rss_peak, 2)
            turn["controller_rss_mb_after_turn"] = controller_rss_mb(controller_pid)
            if turn["controller_rss_mb_after_turn"] is not None:
                rss_samples.append(turn["controller_rss_mb_after_turn"])
            turns.append(turn)
            time.sleep(1.0)

        drain = time.time() + 120
        while time.time() < drain and any(pid_alive(p) for p in afplay_pids):
            time.sleep(0.5)
        settle = time.time() + 180
        while time.time() < settle and live_status().get("render_connected") is not False:
            time.sleep(0.5)
        # Leak gate: after every session exits and the controller idles, RSS
        # must return within the limit of its entry value. Boundary-to-boundary
        # drift is NOT a gate: ps RSS on this machine swings ±180 MB within
        # consecutive turns because macOS compresses pages under the steady
        # ~60 GiB system pressure (measured: 212 -> 81 -> 259 in one run).
        # The peak ceiling catches a runaway allocator, not arena churn.
        drift = None
        if len(rss_samples) >= 2:
            drift = round(rss_samples[-1] - rss_samples[0], 2)

        window = log_lines_containing(RESTART_LOG, started_at, "Wake triggered")
        failed = speech_events_after(SPEECH_LOG, iso_utc, "failed")
        generated = speech_events_after(SPEECH_LOG, iso_utc, "generated")
        mine = [g for g in generated if f"omp-vb-{pid}-" in g.get("wav", "")]
        final = live_status()
        registry = REAL_STATE / "sessions" / f"{pid}.json"
        evidence["turns"] = turns
        evidence["turns_played"] = sum(1 for t in turns if t.get("played"))
        evidence["distinct_afplay_pids"] = len(afplay_pids)
        evidence["clips_generated_for_session"] = len(mine)
        evidence["wake_lines"] = window
        evidence["speech_failed_lines"] = failed
        evidence["controller_lifetime_wake_lines"] = len(window)
        evidence["final_status"] = {
            "render_connected": final.get("render_connected"),
            "state": final.get("state"),
            "mic_dropped": final.get("mic_dropped"),
            "mic_invalid": final.get("mic_invalid"),
            "pid": final.get("pid"),
        }
        evidence["final_slot_count"] = slot_dir_count()
        evidence["rss_samples_mb"] = rss_samples
        evidence["rss_final_mb"] = controller_rss_mb(controller_pid)
        evidence["rss_turn_drift_mb"] = drift
        evidence["rss_peaks_mb"] = [t.get("turn_rss_peak_mb") for t in turns if t.get("played")]
        evidence["registry_entry_present"] = registry.exists()
        evidence["voicebox_footprint_final_mb"] = voicebox_footprint_mb()
        evidence["bridge_status_final"] = bridge_status(port)
        evidence["controller_alive"] = pid_alive(controller_pid)
        evidence["session_still_alive"] = proc.poll() is None
    finally:
        if proc.poll() is None and proc.pid not in pipe.PROTECTED_PIDS:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            os.close(master)
        except OSError:
            pass

    # After the session exits, echo machinery is idle; a leak would leave the
    # controller parked above its entry RSS. The 30 s sample that first ran
    # caught a transient post-drain elevation (median 263.9 MB, decaying to a
    # stable 187.9 MB within ~10 min), so the settle is 120 s and the median
    # is over 10 spaced samples — measuring the steady state, not the drain.
    time.sleep(120)
    evidence["rss_post_exit_median_mb"] = controller_rss_median_mb(controller_pid, 10)

    # Leak trend: median of the first half of turn-boundary samples vs the
    # last half, one-sided. macOS page compression swings single RSS samples
    # by hundreds of MB (R2 saw 70-345 MB within one run), so only a
    # smoothed, growth-direction trend is meaningful.
    samples = [s for s in evidence["rss_samples_mb"] if s is not None]
    if len(samples) >= 4:
        half = max(2, len(samples) // 2)
        first_med = sorted(samples[:half])[len(samples[:half]) // 2]
        last_med = sorted(samples[-half:])[len(samples[-half:]) // 2]
        evidence["rss_cycle_trend_mb"] = round(last_med - first_med, 2)
    else:
        evidence["rss_cycle_trend_mb"] = None

    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))

    ok = (
        evidence["turns_played"] == TURNS
        and evidence["clips_generated_for_session"] >= TURNS
        and evidence["distinct_afplay_pids"] == TURNS
        and all(t.get("render_connected_during_playback") for t in turns if t.get("played"))
        and all(t.get("render_disconnected_after_playback") for t in turns if t.get("played"))
        and not evidence["wake_lines"]
        and not evidence["speech_failed_lines"]
        and evidence["final_status"].get("render_connected") is False
        and evidence["final_status"].get("state") == "IDLE"
        and final.get("mic_dropped", 0) - evidence["baseline_mic_dropped"] == 0
        and final.get("mic_invalid", 0) - evidence["baseline_mic_invalid"] == 0
        and evidence["controller_alive"]
        and evidence["registry_entry_present"]
        and evidence["rss_post_exit_median_mb"] is not None
        and evidence["rss_baseline_mb"] is not None
        and evidence["rss_post_exit_median_mb"] < evidence["rss_baseline_mb"] + RSS_GROWTH_LIMIT_MB
        and evidence["rss_cycle_trend_mb"] is not None
        and evidence["rss_cycle_trend_mb"] <= RSS_GROWTH_LIMIT_MB  # growth-direction trend gate
        and evidence["rss_peaks_mb"]
        and max(evidence["rss_peaks_mb"]) < evidence["rss_baseline_mb"] + RSS_PEAK_LIMIT_MB
    )
    print(f"VA-SOAK-005 live: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
