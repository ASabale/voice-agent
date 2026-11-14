# VA-CI-001 — Wake/VAD tests get the ONNX models on a fresh environment

**ID:** VA-CI-001
**Checked:** 2026-11-14 19:40 UTC
**Level:** 1, unit + CI-equivalent clean-venv reproduction.

## Failure prevented

Every push to main failed CI with 4 failed wake tests (`onnxruntime NoSuchFile: hey_jarvis_v0.1.onnx`, `silero_vad.onnx`) — run 43542615491 at HEAD `95a77f6`. A CI that is always red hides real regressions, and the same bug hits any fresh install of the controller.

## Root cause (verified, not assumed)

The openWakeWord pip wheel bundles only `.tflite` model files. The controller (and the tests) load models with `inference_framework="onnx"`. The previous ensure routine called `openwakeword.utils.download_models(["hey_jarvis_v0.1"])`, whose per-model existence check is keyed on the **`.tflite`** filename: `if not os.path.exists(target_directory/<url-name>)` — the bundled `.tflite` exists, so the `.onnx` download is silently skipped. The feature-model loop has the same flaw. `Model.__init__` does not auto-download. Deterministic, environment-independent.

## Reproduction

In a clean Python 3.12 venv (`/tmp/ci-venv312`, the same interpreter class CI uses), delete the `.onnx` files from `openwakeword/resources/models`, then:
`python -c "from openwakeword.model import Model; Model(wakeword_models=['hey_jarvis'], inference_framework='onnx')"` → `NoSuchFile`, matching the CI traceback byte-for-byte.

## Change

- `bin/omp-voice-controller` `ensure_wake_models()`: resolves each needed ONNX (`melspectrogram.onnx`, `embedding_model.onnx`, `silero_vad.onnx`, `hey_jarvis_v0.1.onnx`) by name from openWakeWord's `FEATURE_MODELS`/`VAD_MODELS`/`MODELS` registries and downloads the `.onnx` variant directly; raises if the registry lacks a name.
- `tests/conftest.py`: session fixture with the same by-name logic, plus a post-download assertion so a failed fetch fails loudly instead of surfacing as NoSuchFile inside a test.
- New regression test `tests/test_wake_models.py` (2 tests, network-free): tflite-bundled-only state must produce all four ONNX files and must not fetch unrelated models; present-ONNX state must download nothing.

## Tests run

- `pytest tests/test_wake_models.py -q` → 2 passed.
- `pytest tests/ -q` in main venv → **253 passed**.
- `pytest tests/ -q` in the clean `/tmp/ci-venv312` (the exact CI command sequence: `py_compile bin/omp-voice-controller bin/playback_state.py` then `pytest tests/`) → **253 passed**; the fixture re-downloaded all four ONNX files from GitHub releases.
- Node job unaffected: `node --experimental-strip-types --test` on the five test files → 88 passed (unchanged code, verified this session).

## Limitations

- CI will stay red until the fix is pushed; the loop does not commit. After the push, the run on the new HEAD must be observed before this row is called "CI green" in the live pipeline.
- The CI venv reproduction used the real network for the download; the unit test simulates it offline.
