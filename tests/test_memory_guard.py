"""VoiceBox/Handy memory limits (live 2026-11-21: VoiceBox reached 37-61 GB)."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_memory_guard", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def _setup(monkeypatch, vb_gb: float, handy_gb: float, speaking: bool) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(controller, "voicebox_footprint_gb", lambda: vb_gb)
    monkeypatch.setattr(controller, "handy_footprint_gb", lambda: handy_gb)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: speaking)
    monkeypatch.setattr(controller, "restart_voicebox", lambda: calls.append("voicebox"))
    monkeypatch.setattr(controller, "warm_voicebox", lambda: calls.append("warm"))
    monkeypatch.setattr(controller, "restart_handy", lambda: calls.append("handy"))
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: calls.append("silence"))
    return calls


def test_over_limit_voicebox_restarts_only_when_quiet(monkeypatch) -> None:
    mic = controller.MicState()
    calls = _setup(monkeypatch, 8.0, 0.3, speaking=True)
    controller.memory_guard_step(mic, 1000.0, {})
    assert calls == []  # mid-reply and under 2x: wait
    calls = _setup(monkeypatch, 8.0, 0.3, speaking=False)
    mic.state = "DICTATING"
    controller.memory_guard_step(mic, 1000.0, {})
    assert calls == []  # never under the user's dictation
    mic.state = "IDLE"
    mic.last_tts_seen = 990.0
    last: dict = {}
    controller.memory_guard_step(mic, 1000.0, last)
    assert calls == []  # a reply played 10 s ago: may be between sentences
    controller.memory_guard_step(mic, 1030.0, last)
    assert calls == ["voicebox", "warm"]
    controller.memory_guard_step(mic, 1060.0, last)
    assert calls == ["voicebox", "warm"]  # backoff: one restart per window


def test_critical_voicebox_is_silenced_and_restarted(monkeypatch) -> None:
    calls = _setup(monkeypatch, 61.0, 0.3, speaking=True)
    controller.memory_guard_step(controller.MicState(), 1000.0, {})
    assert calls == ["silence", "voicebox", "warm"]


def test_handy_restarts_only_when_idle_and_fn_up(monkeypatch) -> None:
    calls = _setup(monkeypatch, 5.0, 3.0, speaking=False)
    mic = controller.MicState()
    mic.fn_was_down = True
    controller.memory_guard_step(mic, 1000.0, {})
    assert calls == []
    mic.fn_was_down = False
    controller.memory_guard_step(mic, 1000.0, {})
    assert calls == ["handy"]
