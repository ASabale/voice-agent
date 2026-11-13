#!/usr/bin/env python3
"""Interrupt real VoiceBox playback with the stop fixture. No microphone.

Posts only to the omp process this script starts. Clip kills are limited to
that pid. Controller pid 64238 and OMP pid 16590 are not signaled.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import select
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_fixture_pipeline as pipe  # noqa: E402

REAL_STATE = pipe.REAL_STATE
PROTECTED = pipe.PROTECTED_PIDS


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


def afplay_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main() -> int:
    if not pipe.voicebox_healthy():
        print("VoiceBox is not healthy. Not launching a server.")
        return 2
    proc, record, master = pipe.start_omp()

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
    if pid in PROTECTED or port == 62283:
        proc.terminate()
        raise SystemExit(f"refusing protected session {pid} {port}")
    state = ROOT / ".local" / "voice-agent" / "fixture-041" / "state"
    os.environ["OMP_VOICE_STATE_DIR"] = str(state)
    os.environ["OMP_VOICE_BRIDGE_ONLY"] = f"http://127.0.0.1:{port}"
    os.environ["OMP_VOICE_PLAYBACK_PID"] = str(pid)
    os.environ["OMP_VOICE_PLAYBACK_DIR"] = str(REAL_STATE / "tts-playing")
    os.environ["OMP_VOICE_HANDY"] = "transcribe-file"
    os.environ["OMP_VOICE_BARGE_TRACE"] = "1"
    loader = importlib.machinery.SourceFileLoader(
        "omp_voice_controller_interrupt", str(ROOT / "bin" / "omp-voice-controller")
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec and spec.loader
    controller = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = controller
    spec.loader.exec_module(controller)
    evidence: dict = {"id": "VA-INT-AUTO-041", "omp_pid": pid, "bridge_port": port, "microphone_opened": False}
    try:
        oww, vad, jobs = controller.load_fixture_listeners()
        sent = post(
            port,
            "Respond with exactly: The quick brown fox jumps over the lazy dog and then counts slowly from one to twelve. Send prompt.",
        )
        evidence["submit"] = sent.get("action")
        playing = pipe.wait_playing(pid, 90)
        if not playing:
            evidence["playback_started"] = False
            print(json.dumps(evidence, indent=2))
            return 1
        afplay = int(playing["afplay_pid"])
        evidence["afplay_pid"] = afplay
        evidence["playback_started"] = True
        time.sleep(0.4)
        mic = controller.MicState()
        mic.last_manual_check = 1e12
        stop = pipe.load_wav(ROOT / "tests" / "fixtures" / "stop-say.wav")
        pipe.feed(
            controller,
            controller.FixtureAudioSource([(stop, 0.6)], pace=True),
            mic,
            oww,
            vad,
            jobs,
        )
        deadline = time.time() + 3
        while time.time() < deadline and afplay_alive(afplay):
            time.sleep(0.05)
        dead = not afplay_alive(afplay)
        onset = mic.barge_onset_wall
        evidence["stopped"] = dead
        evidence["latency_s"] = round(time.time() - onset, 3) if onset and dead else None
        evidence["whisper_text"] = next((row.get("text") for row in reversed(mic.barge_trace) if row.get("stage") == "whisper"), None)
        evidence["stages"] = [row.get("stage") for row in mic.barge_trace]
        time.sleep(0.8)
        evidence["resumed"] = afplay_alive(afplay)
        second = post(port, "Reply with exactly: Second voice check complete. Send prompt.")
        evidence["second_action"] = second.get("action")
        evidence["second_playback"] = bool(pipe.wait_playing(pid, 60))
        evidence["state"] = mic.state
    finally:
        controller._daemon_running.clear()
        if proc.poll() is None and proc.pid not in PROTECTED:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        os.close(master)
        reg = REAL_STATE / "sessions" / f"{pid}.json"
        if reg.exists():
            try:
                data = json.loads(reg.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
            if data.get("pid") == pid:
                reg.unlink()
    out = ROOT / ".local" / "voice-agent" / "runs" / "VA-INT-AUTO-041.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence.get("stopped") and not evidence.get("resumed") and evidence.get("second_playback") else 1


if __name__ == "__main__":
    raise SystemExit(main())
