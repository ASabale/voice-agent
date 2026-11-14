"""The guardian-to-extension file contract, exercised through the real write path.

`pressure.json` is the only channel between the memory guardian and the voice
extension. The policy tests in test_memory_guardian_policy.py stub
`write_pressure`, so nothing else proves the payload the guardian actually
publishes matches what `readMemoryPressure` parses. A renamed or dropped key
parses as "no pressure" and silently disables the deferral. This test runs the
guardian's verbatim `write_pressure` (only the sensors are synthetic) and pins
the field names, types, and the shed/headroom boundary against the fixture the
Node suite consumes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import pytest

GUARDIAN = Path.home() / ".local/bin/strata-memory-ceiling"
FIXTURE = Path(__file__).parent / "fixtures" / "guardian-pressure.json"
GIB = 1024**3

# The keys the extension reads plus the observability fields it ignores.
CONTRACT_KEYS = {"at", "systemUsedGiB", "headroomGiB", "pressureLevel", "freePercent", "shedVoice", "llmBusy"}

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or not GUARDIAN.is_file(),
    reason="the memory guardian is a macOS-local component; not installed here",
)


def load_guardian():
    source = GUARDIAN.read_text(encoding="utf-8")
    module = types.ModuleType("strata_memory_ceiling_contract")
    module.__file__ = str(GUARDIAN)
    exec(compile(source, str(GUARDIAN), "exec"), module.__dict__)
    return module


def publish(mod, used_gib: float) -> dict:
    """Run the guardian's real atomic write path against a synthetic snapshot."""
    tmp = Path(tempfile.mkdtemp())
    mod.STATE_DIR = tmp
    mod.PRESSURE_PATH = tmp / "pressure.json"
    mod._strata_slot_busy = lambda: True
    used = int(used_gib * GIB)
    snap = {
        "systemUsedBytes": used,
        "headroomBytes": mod.TOTAL_RAM_BYTES - used,
        "pressureLevel": 4,
        "freePercent": 25,
    }
    mod.write_pressure(snap, snap["systemUsedBytes"] >= mod.VOICE_SHED_BYTES)
    return json.loads((tmp / "pressure.json").read_text(encoding="utf-8"))


def test_the_write_path_publishes_the_exact_field_set():
    payload = publish(load_guardian(), 61.4)
    assert set(payload) == CONTRACT_KEYS
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["at"])
    assert isinstance(payload["shedVoice"], bool)
    assert isinstance(payload["headroomGiB"], float)
    assert isinstance(payload["llmBusy"], bool)


def test_shed_flag_and_headroom_never_disagree():
    """The extension defers when shedVoice is true OR headroom < 3 GiB. If a
    snapshot ever set headroom below the deferral bound without setting the
    flag, a clock skew or rounding change would silently skip the deferral.
    Assert the boundary is consistent at the shed line."""
    for used_gib in (60.0, 60.9, 61.0, 61.5, 62.0):
        payload = publish(load_guardian(), used_gib)
        assert payload["shedVoice"] is (used_gib >= 61.0)
        if payload["headroomGiB"] < 3.0:
            assert payload["shedVoice"], f"headroom {payload['headroomGiB']} GiB without shedVoice"
        assert payload["headroomGiB"] == round((64.0 - used_gib), 2)


def test_committed_fixture_matches_the_installed_guardian():
    """The Node suite parses tests/fixtures/guardian-pressure.json. If the
    guardian's payload shape drifts from the fixture, the Node tests would
    parse a schema the real guardian no longer writes. This is the drift alarm."""
    live = publish(load_guardian(), 61.4)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert set(fixture) == set(live)
    for key, value in fixture.items():
        if key == "at":
            continue
        assert live[key] == value, f"field {key!r}: guardian writes {live[key]!r}, fixture has {value!r}"


def voice_state(mod, payload: dict) -> bool:
    tmp = Path(tempfile.mkdtemp())
    mod.VOICE_PLAYING_PATH = tmp / "tts-playing.json"
    mod.VOICE_PLAYING_PATH.write_text(json.dumps(payload), encoding="utf-8")
    return mod._voice_is_playing()


def test_the_voice_flag_does_not_outlive_its_afplay_pid():
    """Pruning is read-triggered, and the guardian reads only the flat
    projection. A session SIGKILLed mid-clip with no controller read freezes
    `playing: true` forever, permanently disabling the voice-shed tier that
    protects the engine. The pid in the projection is the liveness witness."""
    mod = load_guardian()
    p = subprocess.Popen(["true"])
    pid = p.pid
    p.wait()  # reaped; the pid is dead for sure
    assert voice_state(mod, {"playing": True, "started_at": 1000.0, "pid": pid}) is False

    assert voice_state(mod, {"playing": True, "started_at": 1000.0, "pid": os.getpid()}) is True
    # No witness: stay conservative and defer the unload.
    assert voice_state(mod, {"playing": True}) is True
    assert voice_state(mod, {"playing": True, "pid": "nonsense"}) is True
    assert voice_state(mod, {"playing": False, "pid": os.getpid()}) is False
