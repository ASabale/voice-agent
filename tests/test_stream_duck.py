"""Per-stream ducking: gain file instead of master volume (VD-DUCK-*).

macOS has no public per-process output volume, so ducking the reply without
touching YouTube requires the gain-controlled voice-play player. These tests
pin the controller side of that seam: the duck writes a gain, the restore
writes 1.0, transactions reconcile, and the pid probe recognises the player.
"""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_stream_duck", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def _gain(tmp_path: Path) -> float:
    return json.loads((tmp_path / "stream-gain.json").read_text())["gain"]


def test_stream_duck_writes_gain_not_master_volume(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setenv("OMP_VOICE_STREAM_PLAYER", "1")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    osascript: list[str] = []

    def fake_run(cmd, **_kw):
        osascript.append(cmd[2])
        raise AssertionError("master volume must not be touched in stream mode")

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    state = controller.MicState()
    controller.duck_output_volume(state)
    assert not osascript
    assert _gain(tmp_path) == 0.2
    assert state.tts_stream_gain == 0.2
    assert state.tts_duck_restore is None
    assert controller._duck_ratio == 0.2
    assert json.loads((tmp_path / "duck-state.json").read_text())["stream_gain"] == 0.2


def test_stream_restore_returns_gain_and_ratio(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setenv("OMP_VOICE_STREAM_PLAYER", "1")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    state = controller.MicState()
    controller.duck_output_volume(state)
    assert controller.restore_output_volume(state, now=50.0) is True
    assert _gain(tmp_path) == 1.0
    assert state.tts_stream_gain is None
    assert state.tts_duck_state == "normal"
    assert controller._duck_ratio == 1.0
    assert not (tmp_path / "duck-state.json").exists()


def test_stream_duck_halves_when_ambient_dominates(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setenv("OMP_VOICE_STREAM_PLAYER", "1")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    state = controller.MicState()
    state.echo_full_gain = 30.0
    state.ambient_short = 60.0
    controller.duck_output_volume(state)
    assert _gain(tmp_path) == 0.6


def test_stream_duck_skips_under_minimum_attenuation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "95")
    monkeypatch.setenv("OMP_VOICE_STREAM_PLAYER", "1")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    state = controller.MicState()
    controller.duck_output_volume(state)
    assert state.tts_stream_gain is None
    assert not (tmp_path / "stream-gain.json").exists()


def test_reconcile_restores_stream_duck_after_crash(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OMP_VOICE_STREAM_PLAYER", "1")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    (tmp_path / "stream-gain.json").write_text(json.dumps({"gain": 0.2}))
    (tmp_path / "duck-state.json").write_text(
        json.dumps({"original": None, "target": 20, "state": "ducked", "ducked_at": 1.0, "stream_gain": 0.2})
    )
    controller.reconcile_duck_state()
    assert _gain(tmp_path) == 1.0
    assert not (tmp_path / "duck-state.json").exists()


def test_pid_probe_matches_voice_play(monkeypatch) -> None:
    monkeypatch.setenv("OMP_VOICE_PLAYBACK_PID", "4242")

    def fake_check_output(_cmd, **_kw):
        return (
            "  100 python3 /Users/x/bin/voice-play /tmp/omp-vb-4242-3.wav\n"
            "  101 /usr/bin/afplay /tmp/omp-vb-4242-4.wav\n"
            "  102 /usr/bin/afplay /tmp/other-clip.wav\n"
            "  103 python3 /Users/x/bin/voice-play /tmp/unrelated.wav\n"
        )

    monkeypatch.setattr(controller.subprocess, "check_output", fake_check_output)
    pids = controller._omp_vb_pids()
    assert pids == ["100", "101"]
