"""A down VoiceBox must not be retried on every microphone frame."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_tier", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def _reset(strata: bool) -> None:
    controller._handy_on_light = False
    controller._voicebox_want = None
    controller._voicebox_ok = False
    controller._voicebox_retry_at = 0.0
    controller._logged_once.discard("voicebox-health")
    if strata:
        controller._strata_loaded.set()
    else:
        controller._strata_loaded.clear()


def test_a_down_voicebox_is_not_retried_every_frame(monkeypatch) -> None:
    health = {"n": 0}
    handy = {"n": 0}

    def fake_health(_strata: bool) -> bool:
        health["n"] += 1
        return False

    def fake_handy(strata: bool) -> None:
        handy["n"] += 1
        controller._handy_on_light = strata

    monkeypatch.setattr(controller, "apply_voicebox_model", fake_health)
    monkeypatch.setattr(controller, "apply_handy_model", fake_handy)
    _reset(True)
    controller.sync_speech_tier(10.0)
    controller.sync_speech_tier(10.08)
    controller.sync_speech_tier(14.9)
    assert health["n"] == 1
    assert handy["n"] == 1
    assert controller._handy_on_light is True
    controller.sync_speech_tier(15.0)
    assert health["n"] == 2
    assert handy["n"] == 1
    _reset(False)


def test_a_confirmed_voicebox_is_not_polled_until_strata_changes(monkeypatch) -> None:
    health = {"n": 0}

    def fake_health(_strata: bool) -> bool:
        health["n"] += 1
        return True

    monkeypatch.setattr(controller, "apply_voicebox_model", fake_health)
    monkeypatch.setattr(controller, "apply_handy_model", lambda strata: None)
    _reset(False)
    controller._handy_on_light = False
    controller.sync_speech_tier(20.0)
    controller.sync_speech_tier(20.08)
    assert health["n"] == 1
    controller._strata_loaded.set()
    controller.sync_speech_tier(20.1)
    assert health["n"] == 2
    _reset(False)


def test_a_large_log_keeps_one_backup(tmp_path) -> None:
    log = tmp_path / "controller.log"
    log.write_text("old-line\n", encoding="utf-8")
    assert controller.rotate_log(log, 4) is True
    assert not log.exists()
    assert (tmp_path / "controller.log.1").read_text(encoding="utf-8") == "old-line\n"
    log.write_text("next-line\n", encoding="utf-8")
    assert controller.rotate_log(log, 4) is True
    assert (tmp_path / "controller.log.1").read_text(encoding="utf-8") == "next-line\n"
    assert controller.rotate_log(log, 100) is False
    assert controller.rotate_log(tmp_path / "missing.log", 4) is False
