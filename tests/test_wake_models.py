"""CI baseline regression: openWakeWord bundles .tflite only.

The wheel ships the tflite models but not the ONNX files, and
openwakeword.utils.download_models() skips a model whose .tflite already
exists. A fresh environment therefore never gets hey_jarvis_v0.1.onnx or
silero_vad.onnx, and every wake test dies with onnxruntime NoSuchFile —
the exact CI failure on 2026-11-14 (run 43542615491).
"""

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_models", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

_RELEASES = "https://github.com/braunshil/openwakeword/releases/download/v0.6.0"


def _fake_openwakeword(models_dir: Path) -> types.ModuleType:
    fake = types.ModuleType("openwakeword")
    # ensure_wake_models derives models_dir from openwakeword.__file__ as
    # Path(__file__).parent / "resources" / "models".
    fake.__file__ = str(models_dir.parent.parent / "openwakeword.py")
    fake.FEATURE_MODELS = {
        "melspectrogram": {"download_url": f"{_RELEASES}/melspectrogram.tflite"},
        "embedding_model": {"download_url": f"{_RELEASES}/embedding_model.tflite"},
    }
    fake.VAD_MODELS = {"silero_vad": {"download_url": f"{_RELEASES}/silero_vad.onnx"}}
    fake.MODELS = {
        "hey_jarvis": {"download_url": f"{_RELEASES}/hey_jarvis_v0.1.tflite"},
        "alexa": {"download_url": f"{_RELEASES}/alexa_v0.1.tflite"},
    }
    utils = types.ModuleType("openwakeword.utils")

    def download_file(url: str, target_directory: str) -> None:
        Path(target_directory, url.split("/")[-1]).write_text(f"pretend model: {url}", encoding="utf-8")

    utils.download_file = download_file
    fake.utils = utils
    return fake


def _install_fake_openwakeword(monkeypatch: pytest.MonkeyPatch, models_dir: Path) -> types.ModuleType:
    fake = _fake_openwakeword(models_dir)
    # Both names must be in sys.modules so `from openwakeword.utils import ...`
    # resolves without touching the real package machinery.
    monkeypatch.setitem(sys.modules, "openwakeword", fake)
    monkeypatch.setitem(sys.modules, "openwakeword.utils", fake.utils)
    monkeypatch.setattr(controller, "log", lambda *_args: None)
    return fake


def _tflite_only(models_dir: Path) -> None:
    models_dir.mkdir(parents=True, exist_ok=True)
    for name in ("melspectrogram.tflite", "embedding_model.tflite", "hey_jarvis_v0.1.tflite"):
        (models_dir / name).write_text("bundled stub", encoding="utf-8")


def test_ensure_wake_models_fetches_onnx_when_only_tflite_is_bundled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models_dir = tmp_path / "resources" / "models"
    _tflite_only(models_dir)
    _install_fake_openwakeword(monkeypatch, models_dir)

    controller.ensure_wake_models()

    for name in ("melspectrogram.onnx", "embedding_model.onnx", "silero_vad.onnx", "hey_jarvis_v0.1.onnx"):
        assert (models_dir / name).exists(), f"{name} was not fetched although the controller loads it"
    # The bundled tflite must not be re-downgraded into a wake download skip.
    assert not (models_dir / "alexa_v0.1.onnx").exists()


def test_ensure_wake_models_is_a_noop_when_onnx_files_are_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models_dir = tmp_path / "resources" / "models"
    _tflite_only(models_dir)
    for name in ("melspectrogram.onnx", "embedding_model.onnx", "silero_vad.onnx", "hey_jarvis_v0.1.onnx"):
        (models_dir / name).write_text("present", encoding="utf-8")
    downloaded: list[str] = []
    fake = _install_fake_openwakeword(monkeypatch, models_dir)

    def spy(url: str, target_directory: str) -> None:
        downloaded.append(url)

    fake.utils.download_file = spy

    controller.ensure_wake_models()
    assert downloaded == []
