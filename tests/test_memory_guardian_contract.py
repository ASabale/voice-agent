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
import signal
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


def stop_engine_probe(mod, *, target: str, behavior: str = "ok",
                      survivors: tuple[list[int], list[int]] = ([], [])):
    """Run the real `stop_engine` with kill/supervisor side effects recorded.

    `survivors` is what the post-SIGTERM `scan_processes()` finds 1.5 s later:
    pids still alive get escalated to SIGKILL. Stubbing it keeps the test
    deterministic and never touches real processes.
    """
    tmp = Path(tempfile.mkdtemp())
    mod.STATE_DIR = tmp
    mod.LAST_PATH = tmp / "memory-ceiling-last.json"
    kills: list[tuple[int, int]] = []
    argvs: list[list[str]] = []

    class FakeSubprocess:
        TimeoutExpired = subprocess.TimeoutExpired
        DEVNULL = subprocess.DEVNULL

        def run(self, argv, **kwargs):
            argvs.append(list(argv))
            if behavior == "timeout":
                raise subprocess.TimeoutExpired(argv, 10)
            if behavior == "oserror":
                raise OSError("supervisor gone")
            return None

    logs: list[str] = []
    fake_os = types.SimpleNamespace(
        kill=lambda pid, sig: kills.append((pid, sig)),
        replace=os.replace,
        path=os.path,
    )
    fake_time = types.SimpleNamespace(
        time=mod.time.time,
        gmtime=mod.time.gmtime,
        strftime=mod.time.strftime,
        sleep=lambda seconds: None,
    )
    saved = (mod.os, mod.subprocess, mod.log_line, mod.scan_processes, mod.time)
    mod.os = fake_os
    mod.subprocess = FakeSubprocess()
    mod.log_line = lambda text: logs.append(text)
    mod.scan_processes = lambda: {"strataPids": list(survivors[0]), "mtplxPids": list(survivors[1])}
    mod.time = fake_time
    snap = {
        "footprintBytes": 46 * GIB,
        "systemUsedBytes": 62 * GIB,
        "wiredBytes": 40 * GIB,
        "otherBurdenBytes": 12 * GIB,
        "headroomBytes": 2 * GIB,
        "freePercent": 15,
        "pressureLevel": 4,
        "swapBytes": 1 * GIB,
        "swapGrowthBytes": 0,
        "pids": [101, 102],
        "mtplxPids": [201],
        "topOtherApps": [],
    }
    try:
        mod.stop_engine("dual_engine_conflict" if target == "mtplx" else "system_memory", snap, target=target)
    finally:
        mod.os, mod.subprocess, mod.log_line, mod.scan_processes, mod.time = saved
    return kills, argvs, logs, json.loads(mod.LAST_PATH.read_text(encoding="utf-8"))


def test_a_targeted_stop_never_signals_the_engine_it_means_to_keep():
    """Rule 0 kills the secondary engine. A stray SIGTERM to the Strata pid
    would drop the 46 GiB model the voice loop is mid-request on — the exact
    failure mode the tiering was built to avoid."""
    kills, argvs, logs, record = stop_engine_probe(load_guardian(), target="mtplx")
    assert kills == [(201, signal.SIGTERM)]
    assert all("runtime stop --profile" not in " ".join(a) for a in argvs)
    assert record["target"] == "mtplx"
    assert record["reason"] == "dual_engine_conflict"
    assert record["pids"] == [101, 102]  # the record documents who stayed up


def test_an_all_stop_signals_every_engine_pid():
    kills, argvs, logs, record = stop_engine_probe(load_guardian(), target="all")
    assert kills == [(101, signal.SIGTERM), (102, signal.SIGTERM), (201, signal.SIGTERM)]
    assert record["target"] == "all"


def test_sigterm_survivors_are_escalated_and_dead_pids_are_not_resignalled():
    """1.5 s after SIGTERM the guardian rescans and SIGKILLs only what is
    still alive. A targeted mtplx stop must never escalate a strata survivor
    — that survivor is precisely the engine the voice loop keeps warm."""
    kills, argvs, logs, record = stop_engine_probe(
        load_guardian(), target="all", survivors=([101], [201])
    )
    assert kills == [
        (101, signal.SIGTERM), (102, signal.SIGTERM), (201, signal.SIGTERM),
        (101, signal.SIGKILL), (201, signal.SIGKILL),
    ]
    kills, _, _, _ = stop_engine_probe(
        load_guardian(), target="mtplx", survivors=([101], [])
    )
    assert (101, signal.SIGKILL) not in kills
    assert kills == [(201, signal.SIGTERM)]  # mtplx exited; no escalation


def test_a_hanging_supervisor_stop_cannot_take_the_watcher_down():
    """The recorded field incident: `TimeoutExpired` escaped `watch()`, launchd
    restarted the guardian with the engine half-dead. Supervisor failures are
    logged, never raised."""
    for behavior, needle in (("timeout", "supervisor stop timed out"),
                             ("oserror", "supervisor stop failed")):
        mod = load_guardian()
        kills, argvs, logs, record = stop_engine_probe(mod, target="all", behavior=behavior)
        assert any(needle in line for line in logs), logs
        # The process kill still happened before the supervisor cleanup.
        assert len(kills) == 3


def test_only_one_watch_instance_can_own_the_slot():
    """The 2026-11-14 field state had two watchers (manual pid 38389 plus the
    launchd unit 38402) running the same kill loop with separate strike
    counters and separate 60 s shed timers. The lock file gives exactly one
    owner; a dead owner's lock is replaced."""
    mod = load_guardian()
    tmp = Path(tempfile.mkdtemp())
    mod.STATE_DIR = tmp
    mod.WATCHER_LOCK_PATH = tmp / "watcher.lock"

    assert mod._claim_watcher_slot() is None
    assert int(mod.WATCHER_LOCK_PATH.read_text()) == os.getpid()

    child = subprocess.Popen(["sleep", "30"])
    mod.WATCHER_LOCK_PATH.write_text(f"{child.pid}\n")
    assert mod._claim_watcher_slot() == child.pid  # live instance refused
    child.kill()
    child.wait()

    assert mod._claim_watcher_slot() is None  # dead owner replaced
    assert int(mod.WATCHER_LOCK_PATH.read_text()) == os.getpid()


def test_a_second_watch_call_exits_before_the_loop():
    mod = load_guardian()
    tmp = Path(tempfile.mkdtemp())
    mod.STATE_DIR = tmp
    mod.WATCHER_LOCK_PATH = tmp / "watcher.lock"
    child = subprocess.Popen(["sleep", "30"])
    mod.WATCHER_LOCK_PATH.write_text(f"{child.pid}\n")
    logs: list[str] = []
    mod.log_line = lambda text: logs.append(text)
    try:
        assert mod.watch() == 0
    finally:
        child.kill()
        child.wait()
    assert any("duplicate watcher" in line for line in logs)


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
