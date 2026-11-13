"""The fixture source yields real frames and does not open the microphone."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import numpy as np

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_audio_source", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def test_fixture_frames_keep_order_and_size_without_a_microphone(monkeypatch) -> None:
    opened = {"mic": False}

    class _Stream:
        def __enter__(self):
            opened["mic"] = True
            return self

        def __exit__(self, *args):
            return None

    class _Sound:
        def InputStream(self, **kwargs):
            return _Stream()

    monkeypatch.setitem(sys.modules, "sounddevice", _Sound())
    speech = np.arange(100, 100 + 1280, dtype=np.int16)
    after = np.full(1280, 7, dtype=np.int16)
    source = controller.FixtureAudioSource([(speech, 0.0), (after, 0.0)], pace=False)
    with source:
        assert source.name == "fixture"
        first = source.read()
        second = source.read()
        assert source.read() is None
    assert first is not None and second is not None
    assert first.shape == (1280,)
    assert second.shape == (1280,)
    assert np.array_equal(first, speech)
    assert int(second[0]) == 7
    assert opened["mic"] is False


def test_bridge_only_and_file_mode_are_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("OMP_VOICE_BRIDGE_ONLY", raising=False)
    monkeypatch.delenv("OMP_VOICE_HANDY", raising=False)
    assert controller.bridge_only_base() is None
    assert controller.handy_file_mode() is False
    monkeypatch.setenv("OMP_VOICE_BRIDGE_ONLY", "9")
    monkeypatch.setenv("OMP_VOICE_HANDY", "transcribe-file")
    assert controller.bridge_only_base() == "http://127.0.0.1:9"
    assert controller.handy_file_mode() is True
    assert controller.SoundDeviceAudioSource.name == "sounddevice"
