"""Wake phrase and clip-gain seams. Grammar is the source of wakes; gain cap is an argument."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_structure", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")

_GRAMMAR = controller.load_command_grammar(_ROOT / "grammar.json")


@pytest.mark.parametrize(
    "phrase",
    [
        "hey jarvis",
        "Hey Jarvis",
        "hey, jarvis",
        "ok jarvis",
        "hello jarvis!",
        "Jarvis",
        "jarvis?",
        "jarvis.",
    ],
)
def test_wake_phrase_accepts_grammar_wakes_and_trailing_punctuation(phrase: str) -> None:
    assert controller.is_wake_phrase(phrase, grammar=_GRAMMAR)


@pytest.mark.parametrize(
    "phrase",
    [
        "heyjarvis",
        " jarvis",
        "hey jarvis please",
        "good morning jarvis",
        "stop",
        "jarvis;",
        "hey. jarvis",
    ],
)
def test_wake_phrase_rejects_non_wakes(phrase: str) -> None:
    assert not controller.is_wake_phrase(phrase, grammar=_GRAMMAR)


def test_clip_for_whisper_uses_the_passed_cap() -> None:
    audio = np.array([0.05, -0.05], dtype=np.float32)
    # peak 0.05 -> 0.5/peak = 10, so the cap is the binding limit
    gained = controller.clip_for_whisper(audio, 6.0)
    assert gained.tolist() == pytest.approx([0.3, -0.3])
    softer = controller.clip_for_whisper(audio, 5.0)
    assert softer.tolist() == pytest.approx([0.25, -0.25])


def test_clip_for_whisper_leaves_near_silence() -> None:
    audio = np.array([0.001, -0.001], dtype=np.float32)
    gained = controller.clip_for_whisper(audio, 6.0)
    assert gained.tolist() == pytest.approx(audio.tolist())
