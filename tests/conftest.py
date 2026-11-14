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
