#!/usr/bin/env python3
"""Feed fixture PCM through the controller. Does not open the microphone.

Isolated state, one OMP process started here, and Handy file transcription.
Does not toggle the shared Handy app, does not post to a protected session,
and does not kill controller pid 64238 or OMP pid 16590.
"""

from __future__ import annotations

import json
import os
import pty
import select
import subprocess
import sys
import threading
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED_PIDS = {16590, 64238}
REAL_STATE = Path.home() / ".local" / "state" / "omp-voice"
RUN_ID = "VA-INT-AUTO-040"


def load_wav(path: Path) -> "object":
    import numpy as np

    with wave.open(str(path)) as handle:
        if handle.getnchannels() != 1 or handle.getframerate() != 16000 or handle.getsampwidth() != 2:
            raise SystemExit(f"{path} is not 16 kHz mono 16-bit")
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).copy()


def say_wav(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["say", "-o", str(path), "--data-format=LEI16@16000", text],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def voicebox_healthy() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:17493/health", timeout=2) as res:
            body = json.loads(res.read().decode())
        return res.status == 200 and bool(body.get("model_loaded"))
    except (OSError, ValueError):
        return False


def newest_session(after: float) -> dict | None:
    directory = REAL_STATE / "sessions"
    if not directory.is_dir():
        return None
    found = None
    for path in directory.glob("*.json"):
        try:
            if path.stat().st_mtime < after - 1:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        pid = data.get("pid")
        port = data.get("port")
        if not isinstance(pid, int) or not isinstance(port, int):
            continue
        if pid in PROTECTED_PIDS or port <= 0:
            continue
        found = data
    return found


def start_omp() -> tuple[subprocess.Popen, dict, int]:
    begun = time.time()
    master, slave = pty.openpty()
    proc = subprocess.Popen(
        ["omp"],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
        cwd="/Users/akshay/Development",
    )
    os.close(slave)
    deadline = time.time() + 25
    record = None
    while time.time() < deadline:
        ready, _, _ = select.select([master], [], [], 0.25)
        if ready:
            try:
                os.read(master, 8192)
            except OSError:
                pass
        record = newest_session(begun)
        if record and record.get("pid") == proc.pid:
            break
        if proc.poll() is not None:
            break
    if not record or record.get("pid") != proc.pid or record.get("pid") in PROTECTED_PIDS:
        if proc.poll() is None and proc.pid not in PROTECTED_PIDS:
            proc.terminate()
        try:
            err = os.read(master, 4000).decode("utf-8", "replace")
        except OSError:
            err = ""
        os.close(master)
        raise SystemExit(f"isolated omp session did not register on its own pid\n{err[-800:]}")
    return proc, record, master


def feed(controller, source, mic, oww, vad, jobs) -> None:
    with source:
        while True:
            frame = source.read()
            if frame is None:
                return
            controller.handle_captured_frame(
                mic,
                frame,
                time.time(),
                "fixture",
                oww,
                vad,
                0.40,
                "hey_jarvis",
                0.50,
                5.0,
                15.0,
                jobs,
            )


def wait_playing(pid: int, timeout: float) -> dict | None:
    slot = REAL_STATE / "tts-playing" / f"{pid}.json"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = json.loads(slot.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.2)
            continue
        if isinstance(data, dict) and data.get("afplay_pid") and not data.get("ended_at"):
            return data
        time.sleep(0.2)
    return None


def main() -> int:
    import numpy as np

    status_path = REAL_STATE / "status.json"
    log_path = REAL_STATE / "controller.log"
    status_before = status_path.stat().st_mtime if status_path.exists() else None
    log_before = log_path.stat().st_mtime if log_path.exists() else None
    if not voicebox_healthy():
        print("VoiceBox is not healthy. Not launching a server.")
        return 2

    work = ROOT / ".local" / "voice-agent" / "fixture-040"
    work.mkdir(parents=True, exist_ok=True)
    first_text = "Respond with exactly: Voice integration test successful. Send prompt."
    second_text = "Reply with exactly: Second voice check complete. Send prompt."
    say_wav(work / "turn1.wav", first_text)
    say_wav(work / "turn2.wav", second_text)
    wake = load_wav(ROOT / "tests" / "fixtures" / "hey-jarvis-say.wav")
    stop = load_wav(ROOT / "tests" / "fixtures" / "stop-say.wav")
    turn1 = load_wav(work / "turn1.wav")
    turn2 = load_wav(work / "turn2.wav")

    proc, record, master = start_omp()

    def drain() -> None:
        while True:
            try:
                ready, _, _ = select.select([master], [], [], 0.5)
            except (OSError, ValueError):
                return
            if not ready:
                continue
            try:
                if not os.read(master, 8192):
                    return
            except OSError:
                return

    threading.Thread(target=drain, daemon=True).start()
    pid = int(record["pid"])
    port = int(record["port"])
    if pid in PROTECTED_PIDS or port == 62283:
        proc.terminate()
        raise SystemExit(f"refusing protected session {pid} {port}")
    state = work / "state"
    os.environ["OMP_VOICE_STATE_DIR"] = str(state)
    os.environ["OMP_VOICE_BRIDGE_ONLY"] = f"http://127.0.0.1:{port}"
    os.environ["OMP_VOICE_PLAYBACK_PID"] = str(pid)
    os.environ["OMP_VOICE_PLAYBACK_DIR"] = str(REAL_STATE / "tts-playing")
    os.environ["OMP_VOICE_HANDY"] = "transcribe-file"

    sys.path.insert(0, str(ROOT / "bin"))
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("omp_voice_controller_fixture_run", str(ROOT / "bin" / "omp-voice-controller"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    controller = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = controller
    spec.loader.exec_module(controller)
    if controller.STATE_DIR != state:
        proc.terminate()
        raise SystemExit(f"controller state dir is {controller.STATE_DIR}")
    print(f"Audio source selected: fixture. Bridge {port}. OMP pid {pid}.")
    oww, vad, jobs = controller.load_fixture_listeners()
    mic = controller.MicState()
    evidence: dict = {
        "id": RUN_ID,
        "audio_source": "fixture",
        "microphone_opened": False,
        "omp_pid": pid,
        "bridge_port": port,
        "handy": "transcribe-file",
        "aec_proved": False,
    }
    try:
        feed(
            controller,
            controller.FixtureAudioSource([(wake, 0.4), (turn1, 5.5)], pace=True),
            mic,
            oww,
            vad,
            jobs,
        )
        evidence["after_turn1_state"] = mic.state
        playing = wait_playing(pid, 90)
        evidence["playback_started"] = bool(playing)
        if playing:
            before_stop = time.time()
            # One short copy goes quiet and releases the hold. Repeat the same
            # fixture with no gap so the barge window can hear it, then leave
            # silence so the clip is sent to Whisper.
            stop_run = np.tile(stop, 6)
            feed(
                controller,
                controller.FixtureAudioSource([(stop_run, 0.6)], pace=True),
                mic,
                oww,
                vad,
                jobs,
            )
            slot = json.loads((REAL_STATE / "tts-playing" / f"{pid}.json").read_text(encoding="utf-8"))
            evidence["stop_slot"] = {
                "ended_at": slot.get("ended_at"),
                "reason": slot.get("reason"),
                "afplay_pid": slot.get("afplay_pid"),
            }
            evidence["stop_latency_s"] = None if not slot.get("ended_at") else round(float(slot["ended_at"]) - before_stop, 3)
        feed(
            controller,
            controller.FixtureAudioSource([(np.zeros(16000, dtype=np.int16), 0.0), (wake, 0.4), (turn2, 5.5)], pace=True),
            mic,
            oww,
            vad,
            jobs,
        )
        evidence["after_turn2_state"] = mic.state
        evidence["second_playback"] = bool(wait_playing(pid, 90))
    finally:
        controller._daemon_running.clear()
        if proc.poll() is None and proc.pid not in PROTECTED_PIDS:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        os.close(master)
    evidence["status_mtime_unchanged"] = status_path.stat().st_mtime == status_before
    evidence["controller_log_mtime_unchanged"] = log_path.stat().st_mtime == log_before
    out = ROOT / ".local" / "voice-agent" / "runs" / f"{RUN_ID}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
