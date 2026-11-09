"""Shared command vectors. Compare action, prefix, and phrase only."""

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_match", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")

_GRAMMAR = controller.load_command_grammar(_ROOT / "grammar.json")
_VECTORS = json.loads((_ROOT / "tests" / "command_vectors.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector", _VECTORS, ids=[v["raw"] for v in _VECTORS])
def test_match_command_vector(vector: dict) -> None:
    matched = controller.match_command(vector["raw"], grammar=_GRAMMAR)
    if vector["action"] is None:
        assert matched is None
        return
    assert matched is not None
    assert matched["action"] == vector["action"]
    assert matched["prefix"] == vector["prefix"]
    assert matched["phrase"] == vector["phrase"]


def test_longest_suffix_beats_shorter_stop() -> None:
    matched = controller.match_command("stop listening", grammar=_GRAMMAR)
    assert matched is not None
    assert matched["phrase"] == "stop listening"
    assert matched["action"] == "paused"
