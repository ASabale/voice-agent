"""The voice-shed tier against a dead or hung VoiceBox.

`shed_voice` is the relief step that runs before the guardian ever touches
the engine. VoiceBox has had no listener on 17493 since the 2026-11-14
SIGABRT, and a half-dead server (health 200 while generation 500s, VA-LAT-001)
is a documented state. Two failure modes matter: an exception escaping the
shed would take the watcher down mid-kill-decision, and an unbounded stall
would delay the sustained kill by the length of the HTTP timeout. Both are
pinned here with synthetic servers; no real VoiceBox is touched.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

import pytest

GUARDIAN = Path.home() / ".local/bin/strata-memory-ceiling"

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or not GUARDIAN.is_file(),
    reason="the memory guardian is a macOS-local component; not installed here",
)

REFUSED_PORT = 17990  # nothing listens here; distinct from the Node mock ranges


def load_guardian():
    source = GUARDIAN.read_text(encoding="utf-8")
    module = types.ModuleType("strata_memory_ceiling_shed")
    module.__file__ = str(GUARDIAN)
    exec(compile(source, str(GUARDIAN), "exec"), module.__dict__)
    return module


def quiet_voice(mod) -> None:
    tmp = Path(tempfile.mkdtemp())
    mod.VOICE_PLAYING_PATH = tmp / "tts-playing.json"
    mod.VOICE_PLAYING_PATH.write_text(json.dumps({"playing": False}), encoding="utf-8")


def hung_voicebox():
    """A server that accepts connections and never answers."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            # Hold the connection; the client times out and closes.
            threading.Thread(target=lambda: time.sleep(20), daemon=True).start()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return srv, srv.getsockname()[1], thread


def test_a_closed_voicebox_is_a_no_op_not_a_crash():
    """Connection refused is the steady state since the SIGABRT. The shed must
    report 'unavailable' and return, never propagate."""
    mod = load_guardian()
    mod.VOICEBOX_API = f"http://127.0.0.1:{REFUSED_PORT}"
    quiet_voice(mod)
    result = mod.shed_voice()
    assert result["freedBytes"] == 0
    assert "unavailable" in result["detail"]


def test_a_hung_voicebox_cannot_stall_the_kill_loop():
    """The half-dead server accepts but never responds. The 5 s urlopen
    timeout bounds the shed; an unbounded wait would push the sustained kill
    out by however long the server hangs."""
    mod = load_guardian()
    srv, port, thread = hung_voicebox()
    mod.VOICEBOX_API = f"http://127.0.0.1:{port}"
    quiet_voice(mod)
    try:
        started = time.monotonic()
        result = mod.shed_voice()
        elapsed = time.monotonic() - started
    finally:
        srv.close()
        thread.join(timeout=1)
    assert "unavailable" in result["detail"]
    assert result["freedBytes"] == 0
    assert elapsed < 8.0, f"shed stalled for {elapsed:.1f}s; the 5s timeout is not enforced"


def test_a_playing_utterance_short_circuits_before_any_http():
    """The gate in watch() is not enough: an utterance can start between the
    gate check and the unload POST. Re-checking the playing flag before opening
    a connection prevents unloading weights mid-generation."""
    mod = load_guardian()
    tmp = Path(tempfile.mkdtemp())
    mod.VOICE_PLAYING_PATH = tmp / "tts-playing.json"
    mod.VOICE_PLAYING_PATH.write_text(
        json.dumps({"playing": True, "started_at": time.time(), "pid": os.getpid()}),
        encoding="utf-8",
    )
    calls: list[str] = []
    mod._http_json = lambda url, payload=None: calls.append(url) or {}
    result = mod.shed_voice()
    assert result == {"freedBytes": 0, "detail": "deferred: utterance in progress"}
    assert calls == []
