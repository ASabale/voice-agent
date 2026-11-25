#!/usr/bin/env python3
"""FN-TTS-001 — fn (Handy push-to-talk) held while VoiceBox is speaking.

Reproduces the live complaint: pressing and holding fn while an omp reply is
being spoken makes Handy's pill flicker, sometimes close on its own, and the
transcript sometimes never lands in the draft.

What is measured, per scenario:
  - every `handy --cancel` / `handy --toggle-transcription` the controller
    makes, with its round-trip time (the controller logs these now)
  - Handy pill presence sampled every 100 ms through System Events
  - every new row in Handy's history.db and when it appeared
  - whether the reply audio died, and when
  - whether the dictated text reached the omp draft (GET /status on the
    session bridge port)

Synthetic fn: CGEventPost of a flags-changed event with
kCGEventFlagMaskSecondaryFn (0x00800000). Verified live: `fn_held()` sees it,
but Handy's own push-to-talk does NOT react to a synthetic fn. So the pill
trace reflects only the controller's own handy calls; scenario "pill-open"
models Handy's own take by opening the pill before the fn edge. Results are
synthetic-fn evidence, not a physical fn press.

Usage: python3 scripts/run_fn_during_tts_probe.py [--label before|after]
                                       [--scenarios a,b,c]
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import pty
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home() / ".local/state/omp-voice"
RUNS = ROOT / ".local/voice-agent/runs"
RUNS.mkdir(parents=True, exist_ok=True)
HANDY_BIN = "/Applications/Handy.app/Contents/MacOS/handy"
HANDY_DB = Path.home() / "Library/Application Support/com.pais.handy/history.db"
FN_MASK = 0x00800000
REPLY_PROMPT = (
    "Reply with about 90 words of plain spoken sentences explaining how a "
    "bicycle gear system works. No lists."
)
SPEECH_TEXT = "the quick brown fox jumps over the lazy dog and records this take"
PILL_POLL_SECONDS = 0.1
RUN_ID = "FN-TTS-001"


def load_cg() -> ctypes.CDLL:
    lib = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
    )
    lib.CGEventSourceFlagsState.argtypes = [ctypes.c_int]
    lib.CGEventSourceFlagsState.restype = ctypes.c_ulong
    lib.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_bool]
    lib.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    lib.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    lib.CGEventSetFlags.restype = None
    lib.CGEventPost.argtypes = [ctypes.c_int, ctypes.c_void_p]
    lib.CGEventPost.restype = None
    return lib


CG = load_cg()


def fn_flags() -> int:
    return int(CG.CGEventSourceFlagsState(1))


def fn_post(down: bool) -> float:
    event = CG.CGEventCreateKeyboardEvent(None, 0, True)
    CG.CGEventSetFlags(event, FN_MASK if down else 0)
    CG.CGEventPost(0, event)
    return time.time()


def fn_held_now() -> bool:
    return bool(fn_flags() & FN_MASK)


class PillTrace:
    """Handy pill presence, sampled every 100 ms by one System Events process."""

    SCRIPT = (
        "tell application \"System Events\"\n"
        "  repeat\n"
        "    try\n"
        "      set c to count windows of process \"handy\"\n"
        "    on error\n"
        "      set c to -1\n"
        "    end try\n"
        "    log c\n"
        "    delay 0.1\n"
        "  end repeat\n"
        "end tell"
    )

    def __init__(self) -> None:
        self.samples: list[tuple[float, int]] = []
        self.stop_event = threading.Event()
        self.proc = subprocess.Popen(
            ["/usr/bin/osascript", "-e", self.SCRIPT],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        for line in self.proc.stderr or []:
            if self.stop_event.is_set():
                return
            try:
                self.samples.append((time.time(), int(line.strip())))
            except ValueError:
                continue

    def stop(self) -> list[tuple[float, int]]:
        self.stop_event.set()
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            pass
        return self.samples

    @staticmethod
    def transitions(samples: list[tuple[float, int]]) -> list[dict]:
        events = []
        previous = None
        for ts, count in samples:
            open_now = count > 0
            if previous is None or open_now != previous[1]:
                events.append({"t": round(ts, 3), "open": open_now, "windows": count})
                previous = (ts, open_now)
        return events

    @staticmethod
    def open_seconds(samples: list[tuple[float, int]]) -> float:
        return round(sum(
            (samples[i + 1][0] - samples[i][0])
            for i in range(len(samples) - 1)
            if samples[i][1] > 0
        ), 2)


class Bridge:
    def __init__(self, pid: int) -> None:
        record = json.loads((STATE / "sessions" / f"{pid}.json").read_text(encoding="utf-8"))
        self.pid = pid
        self.port = int(record["port"])
        self.token = record.get("token") or ""
        self.base = f"http://127.0.0.1:{self.port}"

    def _request(self, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            headers={"Content-Type": "application/json", "x-omp-voice-token": self.token},
            method="POST" if data else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode() or "{}")
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def post(self, text: str, wake: bool = False) -> dict:
        return self._request("/transcript", {"text": text, "wake": wake})

    def status(self) -> dict:
        return self._request("/status")

    def draft(self) -> str:
        status = self.status()
        return str(status.get("draft") or "")


def pid_alive(pid: int) -> bool:
    try:
        subprocess.run(["kill", "-0", str(pid)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def slot(pid: int) -> dict | None:
    path = STATE / "tts-playing" / f"{pid}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def slot_playing(pid: int) -> bool:
    data = slot(pid)
    if not isinstance(data, dict):
        return False
    afplay = data.get("afplay_pid")
    return bool(afplay) and not data.get("ended_at") and pid_alive(int(afplay))


def wait_for_playback(pid: int, timeout: float) -> float | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if slot_playing(pid):
            return time.time()
        time.sleep(0.1)
    return None


def latest_row_id() -> int:
    if not HANDY_DB.exists():
        return 0
    with sqlite3.connect(f"file:{HANDY_DB}?mode=ro", uri=True, timeout=2) as conn:
        return int(conn.execute("SELECT COALESCE(MAX(id),0) FROM transcription_history").fetchone()[0])


def rows_since(after_id: int) -> list[dict]:
    if not HANDY_DB.exists():
        return []
    with sqlite3.connect(f"file:{HANDY_DB}?mode=ro", uri=True, timeout=2) as conn:
        rows = conn.execute(
            "SELECT id, timestamp, COALESCE(post_processed_text, transcription_text, '') "
            "FROM transcription_history WHERE id > ? ORDER BY id",
            (after_id,),
        ).fetchall()
    return [{"id": int(r[0]), "timestamp": r[1], "text": str(r[2])} for r in rows]


def controller_log_since(epoch: float) -> list[dict]:
    lines: list[dict] = []
    for name in ("controller.log", "controller-restart.log"):
        path = STATE / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stamp = line[1:20]
            try:
                epoch_line = time.mktime(time.strptime(stamp, "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                continue
            if epoch_line >= epoch:
                lines.append({"t": stamp, "line": line[22:]})
    return lines


def controller_state() -> dict:
    try:
        out = subprocess.run(
            [str(Path.home() / ".local/bin/omp-voice-controller"), "status"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        start = out.find("{")
        return json.loads(out[start:]) if start >= 0 else {}
    except Exception:
        return {}


def draft_of_delivery() -> tuple[str, int | None]:
    """The draft of whichever session the controller is delivering to."""
    status = controller_state()
    pid = (status.get("delivery") or {}).get("pid")
    if pid is None:
        return "", None
    record = (STATE / "sessions" / f"{pid}.json")
    if not record.exists():
        return "", pid
    data = json.loads(record.read_text(encoding="utf-8"))
    request = urllib.request.Request(
        f"http://127.0.0.1:{data['port']}/status",
        headers={"x-omp-voice-token": data.get("token") or ""},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode() or "{}")
        return str(body.get("draft") or ""), int(pid)
    except Exception:
        return "", int(pid)


def start_omp() -> tuple[subprocess.Popen, Bridge]:
    # omp needs a terminal to start its interactive session (and therefore its
    # voice extension); DEVNULL stdin makes it exit before registering a bridge.
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        ["omp", "--model", "strata/qwen3.8-flash-next-q2_0"],
        stdin=slave,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(Path.home() / "Development"),
    )
    os.close(slave)
    deadline = time.time() + 60
    while time.time() < deadline:
        path = STATE / "sessions" / f"{proc.pid}.json"
        if path.exists():
            return proc, Bridge(proc.pid)
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    raise SystemExit(f"isolated omp session {proc.pid} never registered a bridge")


def make_speech_clip() -> Path:
    clip = RUNS / f"{RUN_ID}-speech-fixture.wav"
    subprocess.run(
        ["say", "-o", str(clip), "--data-format=LEI16@16000", SPEECH_TEXT],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return clip


def speak(clip: Path) -> subprocess.Popen:
    return subprocess.Popen(["afplay", str(clip)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


SCENARIOS = {
    "a": {"name": "hold-3s-talk-immediately", "hold_s": 3.0, "speak": True, "pre_open": False, "fn_before_reply": False},
    "b": {"name": "quick-tap-0.35s", "hold_s": 0.35, "speak": False, "pre_open": False, "fn_before_reply": False},
    "c": {"name": "hold-before-playback", "hold_s": 3.0, "speak": True, "pre_open": False, "fn_before_reply": True},
    "d": {"name": "hold-through-end-of-reply", "hold_s": None, "speak": True, "pre_open": False, "fn_before_reply": False},
    "e": {"name": "pill-already-open-at-fn-edge", "hold_s": 3.0, "speak": True, "pre_open": True, "fn_before_reply": False},
}


def run_scenario(scenario: dict, bridge: Bridge, clip: Path) -> dict:
    name = scenario["name"]
    fn_post(False)  # guarantee a clean key state before the edge
    time.sleep(0.3)
    baseline = latest_row_id()
    log_mark = time.time() - 1.0
    trace = PillTrace()
    fn_states: list[list] = []
    result: dict = {"scenario": name, "synthetic_fn": True}

    def send_reply() -> None:
        bridge.post(REPLY_PROMPT)
        # A bare send phrase submits only with a wake inside the gate, so the
        # probe wakes it explicitly.
        bridge.post("send prompt", wake=True)

    fn_down_at = None
    playback_onset = None
    if scenario["fn_before_reply"]:
        fn_down_at = fn_post(True)
        send_reply()
        # fn is already held, so the controller silences the reply as soon as
        # it tries to start: either audio plays, or the stop is logged.
        deadline = time.time() + 240
        while time.time() < deadline:
            if slot_playing(bridge.pid):
                playback_onset = time.time()
                break
            if any("silencing it" in entry["line"] for entry in controller_log_since(fn_down_at)):
                playback_onset = "silenced-while-held"
                break
            if any("render reference connected" in entry["line"] for entry in controller_log_since(fn_down_at)):
                playback_onset = "started-while-held"
                break
            time.sleep(0.2)
    else:
        send_reply()
        playback_onset = wait_for_playback(bridge.pid, 240)
        if playback_onset:
            # The controller samples playback every 0.24 s; give it a stable
            # window so the fn edge lands while it knows a reply is playing.
            time.sleep(2.0)
            if scenario["pre_open"]:
                subprocess.run([HANDY_BIN, "--toggle-transcription"], check=False)
            fn_down_at = fn_post(True)
    result["fn_down_at"] = fn_down_at
    result["fn_down_seen_by_probe"] = fn_held_now()
    result["playback_onset"] = playback_onset
    if playback_onset is None:
        trace.stop()
        result["error"] = "reply never started playing"
        return result

    speech_proc = speak(clip) if scenario["speak"] else None
    result["speech_played"] = bool(speech_proc)

    if scenario["hold_s"] is None:
        deadline = time.time() + 60
        while time.time() < deadline and slot_playing(bridge.pid):
            time.sleep(0.1)
    else:
        # Sample the synthetic key state throughout the hold so a spurious
        # release inside the controller can be attributed.
        end = time.time() + scenario["hold_s"]
        while time.time() < end:
            fn_states.append([round(time.time() - fn_down_at, 2), fn_held_now()])
            time.sleep(0.2)
    result["fn_held_samples"] = fn_states

    fn_up_at = fn_post(False)
    result["fn_up_at"] = fn_up_at
    result["hold_seconds"] = round(fn_up_at - fn_down_at, 2) if fn_down_at else None
    result["fn_held_confirmed_while_holding"] = fn_held_now()

    # Watch for the pill and the transcript for 12 s after the release. The
    # draft baseline is taken at release because submitting the prompt clears
    # the draft.
    draft_at = None
    row_at = None
    draft_at_release, delivery_pid = draft_of_delivery()
    result["delivery_pid"] = delivery_pid
    result["draft_at_release"] = draft_at_release[:200]
    deadline = time.time() + 12
    while time.time() < deadline:
        if row_at is None and latest_row_id() > baseline:
            row_at = time.time()
        if draft_at is None:
            current_draft, _ = draft_of_delivery()
            if current_draft != draft_at_release:
                draft_at = time.time()
                result["draft_after"] = current_draft[:200]
        if row_at is not None and draft_at is not None:
            break
        time.sleep(0.1)
    samples = trace.stop()
    if speech_proc:
        try:
            speech_proc.wait(timeout=10)
        except Exception:
            pass

    status = controller_state()
    result["pill_samples"] = len(samples)
    result["pill_transitions"] = PillTrace.transitions(samples)
    result["pill_open_seconds"] = PillTrace.open_seconds(samples)
    result["history_rows"] = rows_since(baseline)
    result["row_first_seen_s_after_release"] = round(row_at - fn_up_at, 2) if row_at and fn_up_at else None
    result["draft_first_change_s_after_release"] = round(draft_at - fn_up_at, 2) if draft_at and fn_up_at else None
    result["controller_state_after"] = (status.get("controller") or {}).get("state")
    result["delivery_pid"] = (status.get("delivery") or {}).get("pid")
    result["controller_log"] = controller_log_since(log_mark)
    result["handy_calls"] = [entry for entry in result["controller_log"] if "handy " in entry["line"]]
    result["fn_log"] = [entry for entry in result["controller_log"] if "fn" in entry["line"]]
    bridge.post("clear draft")
    time.sleep(1.0)
    return result


def table(scenarios: list[dict]) -> str:
    header = (
        f"{'scenario':<32}{'hold s':>8}{'cancels':>9}{'toggles':>9}"
        f"{'pill closes':>12}{'pill open s':>12}{'rows':>6}{'draft':>7}"
    )
    lines = [header, "-" * len(header)]
    for scenario in scenarios:
        cancels = sum(1 for entry in scenario.get("handy_calls", []) if "--cancel" in entry["line"])
        toggles = sum(1 for entry in scenario.get("handy_calls", []) if "--toggle" in entry["line"])
        closes = sum(1 for event in scenario.get("pill_transitions", []) if not event["open"])
        draft = "yes" if scenario.get("draft_after") else "no"
        lines.append(
            f"{scenario['scenario']:<32}{scenario.get('hold_seconds') or 0:>8}"
            f"{cancels:>9}{toggles:>9}{closes:>12}{scenario.get('pill_open_seconds', 0):>12}"
            f"{len(scenario.get('history_rows', [])):>6}{draft:>7}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_fn_during_tts_probe.py")
    parser.add_argument("--label", default="run")
    parser.add_argument("--scenarios", default="a,b,c,d,e")
    args = parser.parse_args()

    try:
        with urllib.request.urlopen("http://127.0.0.1:17493/health", timeout=3) as response:
            healthy = json.loads(response.read().decode()).get("model_loaded")
    except Exception:
        healthy = False
    if not healthy:
        print("VoiceBox is not healthy; a human must reopen Voicebox.app")
        return 2
    if not pid_alive(int((STATE / "controller.pid").read_text().strip())):
        print("omp-voice-controller is not running")
        return 3

    proc, bridge = start_omp()
    scenarios = [SCENARIOS[key] for key in args.scenarios.split(",")]
    clip = make_speech_clip()
    evidence: dict = {
        "id": RUN_ID,
        "label": args.label,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "omp_pid": bridge.pid,
        "bridge_port": bridge.port,
        "fn_is_synthetic": True,
        "note": "Reply audio is a real VoiceBox reply; the fn key is synthetic. Handy does not treat a synthetic CGEvent fn as push-to-talk; "
                "the pill trace therefore shows the controller's own handy calls.",
        "scenarios": [],
    }
    try:
        for scenario in scenarios:
            result = run_scenario(scenario, bridge, clip)
            evidence["scenarios"].append(result)
            print(json.dumps({
                "scenario": result["scenario"],
                "hold": result.get("hold_seconds"),
                "cancels": sum(1 for e in result.get("handy_calls", []) if "--cancel" in e["line"]),
                "toggles": sum(1 for e in result.get("handy_calls", []) if "--toggle" in e["line"]),
                "pill_open_s": result.get("pill_open_seconds"),
                "rows": len(result.get("history_rows", [])),
                "draft": bool(result.get("draft_after")),
            }), flush=True)
            # Let the reply finish or the controller settle before the next turn.
            deadline = time.time() + 30
            while time.time() < deadline and slot_playing(bridge.pid):
                time.sleep(0.3)
    finally:
        fn_post(False)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    out = RUNS / f"{RUN_ID}-{args.label}.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(table(evidence["scenarios"]))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
