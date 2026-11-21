import pytest

# openWakeWord's pip wheel bundles only .tflite files, and download_models()
# skips a model when its .tflite exists — so a fresh environment (CI) never
# gets the .onnx files the wake/VAD tests load. Mirrors
# bin/omp-voice-controller's ensure_wake_models().
_REQUIRED_ONNX = ["melspectrogram.onnx", "embedding_model.onnx", "silero_vad.onnx", "hey_jarvis_v0.1.onnx"]


@pytest.fixture(scope="session", autouse=True)
def ensure_wake_models():
    from pathlib import Path

    import openwakeword
    from openwakeword.utils import download_file

    models_dir = Path(openwakeword.__file__).parent / "resources" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    urls = {}
    for group in (openwakeword.FEATURE_MODELS, openwakeword.VAD_MODELS, openwakeword.MODELS):
        for entry in group.values():
            urls[entry["download_url"].split("/")[-1]] = entry["download_url"]
    for name in _REQUIRED_ONNX:
        if (models_dir / name).exists():
            continue
        url = urls.get(name) or urls.get(name.replace(".onnx", ".tflite"))
        if url is None:
            raise RuntimeError(f"openWakeWord does not list a model named {name}")
        download_file(url.replace(".tflite", ".onnx"), str(models_dir))
    missing = [name for name in _REQUIRED_ONNX if not (models_dir / name).exists()]
    if missing:
        raise RuntimeError(f"openWakeWord ONNX models still missing after download: {missing}")


@pytest.fixture(autouse=True)
def isolated_state_dir(monkeypatch, tmp_path):
    """Tests must not read the live ~/.local/state/omp-voice.

    Every test module loads its own copy of the controller. Without this, a
    reply the live omp session is speaking (tts-playing slots) turns on real
    echo cancellation and the speaking probe inside unrelated tests.
    """
    import sys

    state = tmp_path / "omp-voice-state"
    state.mkdir()
    for module in list(sys.modules.values()):
        if hasattr(module, "STATE_DIR") and hasattr(module, "refresh_render_reference"):
            monkeypatch.setattr(module, "STATE_DIR", state)
            for name, leaf in (
                ("SESSION_DIR", "sessions"),
                ("PID_FILE", "controller.pid"),
                ("STATUS_FILE", "status.json"),
                ("LOG_FILE", "controller.log"),
                ("TTS_STATE_FILE", "tts-playing.json"),
            ):
                monkeypatch.setattr(module, name, state / leaf)
