"""Regression tests for the acoustic verification metric in bin/voice-doctor.

`acoustic_score` is the gate that decides whether the speakers actually
emitted a clip (physical loop proof) and it is calibrated on this machine
against real recordings (VD-ACAL-006: playback 0.956, silence 0.376).
These tests pin the math deterministically without touching the audio
device: a speech-band signal in noise must pass, noise alone must fail,
and a ducked (0.35 gain) emission must still pass.
"""

from __future__ import annotations

import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "bin" / "voice-doctor"
RATE = 48000


def load_doctor():
    module = types.ModuleType("voice_doctor")
    module.__file__ = str(DOCTOR)
    exec(DOCTOR.read_text(encoding="utf-8"), module.__dict__)
    return module


def speech_target(seconds: float = 3.0) -> np.ndarray:
    """Speech-like signal: 700 Hz carrier gated by syllable-length bursts."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    carrier = np.sin(2 * np.pi * 700 * t)
    # 250 ms on / 150 ms off bursts with 40 ms ramps.
    envelope = np.zeros(n)
    for i, start in enumerate(range(0, n, int(0.4 * RATE))):
        end = min(start + int(0.25 * RATE), n)
        envelope[start:end] = 1.0
    envelope = np.convolve(envelope, np.ones(int(0.04 * RATE)) / 40, mode="same")
    return carrier * envelope * 0.3


def floor_noise(seconds: float = 5.0) -> np.ndarray:
    """Room ambient: low-frequency hum plus weak broadband hiss."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    hum = 0.01 * np.sin(2 * np.pi * 60 * t) + 0.004 * np.sin(2 * np.pi * 120 * t)
    hiss = 0.003 * np.random.default_rng(7).standard_normal(n)
    return hum + hiss


def test_emitted_clip_passes_against_ambient():
    doctor = load_doctor()
    target = speech_target()
    rec = floor_noise(5.0)
    rec[: len(target)] += 0.8 * target  # playback starts at t=0
    score = doctor.acoustic_score(target, rec)
    assert score["ok"], f"real playback rejected: {score}"
    assert score["correlation"] > 0.6
    assert score["peak_over_floor"] >= 3.0


def test_ducked_playback_still_passes():
    doctor = load_doctor()
    target = speech_target()
    rec = floor_noise(5.0)
    rec[: len(target)] += 0.35 * target  # gain-ducked emission
    score = doctor.acoustic_score(target, rec)
    assert score["ok"], f"ducked playback rejected: {score}"


def test_silence_fails():
    doctor = load_doctor()
    target = speech_target()
    score = doctor.acoustic_score(target, floor_noise(5.0))
    assert not score["ok"], f"ambient noise accepted as speech: {score}"
    assert score["correlation"] <= 0.6 or score["peak_over_floor"] < 3.0


def test_offset_playback_still_found():
    """The room path delays playback; the scan must find the shifted window."""
    doctor = load_doctor()
    target = speech_target()
    rec = floor_noise(6.0)
    delay = int(0.5 * RATE)
    rec[delay : delay + len(target)] += 0.7 * target
    score = doctor.acoustic_score(target, rec)
    assert score["ok"], f"delayed playback rejected: {score}"
    assert score["best_offset_ms"] >= 400
