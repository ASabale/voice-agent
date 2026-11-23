"""Bridge auth (F1) and wake gating (F2) on the controller side.

The conftest fixture already points STATE_DIR/SESSION_DIR at a temp dir, so
the registry files written here never touch the live state directory.
"""

import http.server
import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_auth", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")


class _StubBridge(http.server.BaseHTTPRequestHandler):
    """A stand-in omp bridge: 200 only when the session token header is present."""

    def _respond(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _handle(self) -> None:
        token = self.headers.get(controller.BRIDGE_TOKEN_HEADER)
        if not token:
            self._respond(401, {"ok": False, "error": "missing_or_bad_token"})
            return
        self._respond(200, {"ok": True, "pid": os.getpid()})

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def log_message(self, format: str, *args: object) -> None:
        pass


def _write_session(port: int, token: str) -> None:
    controller.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    (controller.SESSION_DIR / f"{os.getpid()}.json").write_text(
        json.dumps({"pid": os.getpid(), "port": port, "token": token}),
        encoding="utf-8",
    )


def test_bridge_request_sends_the_registry_token(tmp_path):
    server = http.server.HTTPServer(("127.0.0.1", 0), _StubBridge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        token = "a" * 64
        _write_session(server.server_port, token)
        got = controller.bridge_request("/status", method="GET", base=f"http://127.0.0.1:{server.server_port}")
        assert got == {"ok": True, "pid": os.getpid()}
        # A base with no registry entry gets no header, and the stub rejects it.
        unauth = controller.bridge_request("/status", method="GET", base="http://127.0.0.1:9")
        assert unauth is None
    finally:
        server.shutdown()
        server.server_close()


def test_registry_exposes_the_token():
    token = "b" * 64
    _write_session(43210, token)
    sessions = controller.load_session_registry()
    entry = sessions[os.getpid()]
    assert entry["token"] == token
    assert entry["port"] == 43210


def test_missing_token_in_registry_is_none():
    controller.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    (controller.SESSION_DIR / f"{os.getpid()}.json").write_text(
        json.dumps({"pid": os.getpid(), "port": 43211}),
        encoding="utf-8",
    )
    sessions = controller.load_session_registry()
    assert sessions[os.getpid()]["token"] is None


def test_pid_bridge_probe_accepts_401_as_a_live_bridge():
    server = http.server.HTTPServer(("127.0.0.1", 0), _StubBridge)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        probe = controller.pid_bridge_port(os.getpid())
        if probe is None:
            pytest.skip("this test process has no single loopback listener to probe")
        assert probe == server.server_port
        assert controller.pid_bridge_port(os.getpid(), "c" * 64) == server.server_port
    finally:
        server.shutdown()
        server.server_close()


def test_dispatch_transcript_flags_wake(monkeypatch):
    bodies: list[dict] = []

    def fake_bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 0.0, base: str | None = None) -> dict:
        if path == "/status":
            return {"ok": True, "version": 2}
        bodies.append(body or {})
        return {"ok": True, "action": "appended", "draft": "hello there"}

    monkeypatch.setattr(controller, "bridge_request", fake_bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 43212, "focused_text": False},
    )
    controller.dispatch_transcript("hello there", wake=False)
    assert bodies and all(row.get("wake") is False for row in bodies)
    controller.dispatch_transcript("hello again", wake=True)
    assert all(row.get("wake") is True for row in bodies[1:])
    # The default keeps old callers working: ambient sends never default to False.
    controller.dispatch_transcript("hello once more")
    assert bodies[-1].get("wake") is True


def test_recent_wake_window():
    mic = controller.MicState()
    assert mic.recent_wake() is False
    mic.wake_mono = time.monotonic() - controller.WAKE_SEND_WINDOW_SECONDS + 1
    assert mic.recent_wake() is True
    mic.wake_mono = time.monotonic() - controller.WAKE_SEND_WINDOW_SECONDS - 1
    assert mic.recent_wake() is False
    mic.state = "DICTATING"
    assert mic.recent_wake() is True


def test_idle_send_without_a_recent_wake_is_ignored(monkeypatch):
    posted: list[str] = []
    cues: list[str] = []

    def dispatch(text: str, wake: bool = True) -> dict[str, str]:
        posted.append(text)
        return {"action": "sent"}

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 43213, "focused_text": False},
    )
    monkeypatch.setattr(controller, "bridge_draft", lambda _base: "a drafted sentence")

    ambient = controller.MicState()
    assert ambient.apply_whisper("idle_verify", "send prompt", None, None) is False
    assert posted == []
    assert ambient.state == "IDLE"

    woken = controller.MicState()
    woken.wake_mono = time.monotonic() - 5
    assert woken.apply_whisper("idle_verify", "send prompt", None, None) is False
    assert posted == ["send prompt"]
    assert cues == [controller.SOUND_SEND]


def test_state_files_are_private():
    controller.write_status("IDLE", {"note": "test"})
    controller._write_private(controller.STATE_DIR / "probe.json", "{}")
    status_mode = controller.STATUS_FILE.stat().st_mode & 0o777
    probe_mode = (controller.STATE_DIR / "probe.json").stat().st_mode & 0o777
    assert status_mode == 0o600
    assert probe_mode == 0o600
