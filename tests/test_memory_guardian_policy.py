"""Policy tests for ~/.local/bin/strata-memory-ceiling with synthetic traces.

The guardian itself is a machine-local component, not repo code. These tests
import the installed script and replace only its sensors and actuators:
`sample()` replays a deterministic trace, `stop_engine`/`shed_voice` record
instead of touching processes, and `time` is a fake clock so grace periods and
rate limits are exact. The decision logic under test is the guardian's own
`watch()` loop, verbatim.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

GUARDIAN = Path.home() / ".local/bin/strata-memory-ceiling"

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or not GUARDIAN.is_file(),
    reason="the memory guardian is a macOS-local component; not installed here",
)

GIB = 1024**3


@pytest.fixture(scope="module")
def guardian():
    # The installed guardian has no .py extension, so importlib cannot infer a
    # loader. Compile it as a module directly; the __name__ guard keeps main()
    # from running.
    source = GUARDIAN.read_text(encoding="utf-8")
    module = types.ModuleType("strata_memory_ceiling")
    module.__file__ = str(GUARDIAN)
    exec(compile(source, str(GUARDIAN), "exec"), module.__dict__)
    return module


def snap(mod, *, used_gib: float, footprint_gib: float = 46.0,
         swap_growth: int = 0, swap_delta: int = 0,
         pressure: int = 4, free: int = 15, swap_bytes: int = 0,
         dual: bool = False) -> dict:
    """One deterministic guardian sample built from GiB-level facts.

    Flags are computed with the guardian's own constants so the trace exercises
    the real thresholds, not hard-coded numbers.
    """
    used = int(used_gib * GIB)
    footprint = int(footprint_gib * GIB)
    headroom = max(0, mod.TOTAL_RAM_BYTES - used)
    return {
        "ok": True,
        "ceilingBytes": mod.CEILING_BYTES,
        "systemUsedKillBytes": mod.SYSTEM_USED_KILL_BYTES,
        "footprintBytes": footprint,
        "strataFootprintBytes": footprint,
        "strataResidentBytes": footprint,
        "mtplxFootprintBytes": 0,
        "otherAppFootprintBytes": int(12 * GIB),
        "otherBurdenBytes": int(12 * GIB),
        "topOtherApps": [],
        "systemUsedBytes": used,
        "wiredBytes": int(footprint * 0.9),
        "appBytes": used - int(8 * GIB),
        "compressorBytes": int(8 * GIB),
        "cachedFileBytes": 0,
        "headroomBytes": headroom,
        "freePercent": free,
        "pressureLevel": pressure,
        "pids": [4242],
        "mtplxPids": [9999] if dual else [],
        "swapBytes": swap_bytes,
        "swapGrowthBytes": swap_growth,
        "swapouts": 1000,
        "swapoutDelta": swap_delta,
        "overCeiling": footprint > mod.CEILING_BYTES,
        "overSystem": used > mod.SYSTEM_USED_KILL_BYTES or headroom < mod.MIN_HEADROOM_BYTES,
        "swapping": (
            headroom < mod.MIN_HEADROOM_BYTES
            and swap_growth >= mod.SWAP_GROWTH_KILL_BYTES
            and swap_delta >= mod.SWAPOUT_DELTA_THRESHOLD
        ),
        "shedVoice": used >= mod.VOICE_SHED_BYTES,
        "emergency": headroom < mod.EMERGENCY_HEADROOM_BYTES,
        "dualEngines": dual,
    }


def run_watch(mod, snaps, *, voice_playing: bool = False, idle_sec: float = 0.0,
              idle_policy: str = "idle", idle_in_flight: bool = False,
              slot_busy: "bool | list[bool]" = False, shed_result: dict | None = None):
    """Run the real watch() loop against a synthetic trace.

    Returns recorded stops (reason, clock time), relief times, pressure-file
    shed flags, and log lines. StopIteration at trace end terminates the loop,
    exactly as a process kill would in the field. A relief time is recorded
    only when an unload actually happened, matching the watch() rule. After a
    recorded stop, later samples report no engine, so traces may continue past
    a kill and assert the rules do not re-fire.
    """

    class Clock:
        def __init__(self):
            self.t = 1000.0

        def time(self):
            return self.t

        def sleep(self, seconds):
            self.t += seconds

        def strftime(self, fmt, struct_time):
            return "2026-11-14T00:00:00Z"

    clock = Clock()
    stops: list[tuple[str, float]] = []
    targets: list[str] = []
    relief_times: list[float] = []
    pressures: list[bool] = []
    logs: list[str] = []
    trace = iter(snaps)
    stopped = False
    mtplx_stopped = False
    sample_count = 0

    names = (
        "time", "sample", "stop_engine", "shed_voice", "write_pressure",
        "log_line", "_voice_is_playing", "_idle_seconds", "_strata_slot_busy",
    )
    original = {name: getattr(mod, name) for name in names}
    try:
        mod.time = clock
        def fake_sample(baseline_swap=None, prev_swapouts=None):
            nonlocal sample_count
            # After a recorded stop the field scan no longer lists the dead
            # engine(s), so the synthetic world agrees: traces can run past a
            # kill and assert the rules do not re-fire on a dead engine.
            snap = next(trace)
            sample_count += 1
            if stopped:
                snap = dict(snap, pids=[], mtplxPids=[], dualEngines=False)
            elif mtplx_stopped:
                snap = dict(snap, mtplxPids=[], dualEngines=False)
            return snap

        mod.sample = fake_sample
        def fake_stop(reason, snap, target="all"):
            nonlocal stopped, mtplx_stopped
            stops.append((reason, clock.t))
            targets.append(target)
            if target == "mtplx":
                mtplx_stopped = True
            else:
                stopped = True

        mod.stop_engine = fake_stop

        def fake_shed():
            result = shed_result if shed_result is not None else {"freedBytes": 2 * GIB, "detail": "test unload"}
            if result["freedBytes"] > 0 or "unloaded" in result["detail"]:
                relief_times.append(clock.time())
            return result

        mod.shed_voice = fake_shed
        mod.write_pressure = lambda snap, shed: pressures.append(shed)
        mod.log_line = lambda text: logs.append(text)
        mod._voice_is_playing = lambda: voice_playing
        mod._idle_seconds = lambda: (idle_sec, idle_policy, idle_in_flight)
        if isinstance(slot_busy, list):
            def fake_slot_busy():
                return slot_busy[min(sample_count, len(slot_busy) - 1)]
            mod._strata_slot_busy = fake_slot_busy
        else:
            mod._strata_slot_busy = lambda: slot_busy
        try:
            mod.watch()
        except StopIteration:
            pass
    finally:
        for name, value in original.items():
            setattr(mod, name, original[name])
    return {"stops": stops, "targets": targets, "relief_times": relief_times,
           "pressures": pressures, "logs": logs}


def test_steady_state_critical_pressure_never_kills(guardian):
    # 62 GiB used with kernel CRITICAL is Flash-Next's normal operating point.
    # Twenty samples must produce no stop and no unload (nothing is tight).
    trace = [snap(guardian, used_gib=62.0) for _ in range(20)]
    result = run_watch(guardian, trace)
    assert result["stops"] == []
    assert result["relief_times"] == []
    assert all(result["pressures"])  # the extension is told to shed voice the whole time


def test_kill_needs_sustained_samples(guardian):
    # Three samples above the 63 GiB line, then recovery: no kill.
    trace = [snap(guardian, used_gib=63.2) for _ in range(3)]
    trace += [snap(guardian, used_gib=58.0) for _ in range(10)]
    result = run_watch(guardian, trace)
    assert result["stops"] == []
    assert result["pressures"][-1] is False


def test_voice_relief_happens_before_the_engine_is_touched(guardian):
    # Sustained 63.2 GiB (headroom 0.8 GiB: over the 1 GiB floor but above the
    # 0.75 GiB emergency line). The unload comes first; the kill waits out the
    # relief grace period; RELIEF_PENDING is logged while waiting.
    trace = [snap(guardian, used_gib=63.2) for _ in range(42)]
    result = run_watch(guardian, trace)
    assert len(result["relief_times"]) == 1
    assert len(result["stops"]) == 1
    reason, stop_at = result["stops"][0]
    assert reason == "system_memory"
    assert stop_at - result["relief_times"][0] >= guardian.RELIEF_GRACE_SEC
    assert any("RELIEF_PENDING" in line for line in result["logs"])


def test_a_kill_clears_the_shed_flag_and_never_repeats(guardian):
    # Once the engine is killed, watch()'s not-running branch rewrites the
    # pressure file with shed=False and resets the strike counter: a trace
    # continuing past the kill shows exactly one stop and a cleared flag.
    trace = [snap(guardian, used_gib=63.2) for _ in range(60)]
    result = run_watch(guardian, trace)
    assert len(result["stops"]) == 1
    assert result["pressures"][-1] is False


def test_zero_headroom_is_an_immediate_stop(guardian):
    # 63.4 GiB used -> 0.6 GiB headroom: nothing can be shed fast enough.
    trace = [snap(guardian, used_gib=63.4)]
    result = run_watch(guardian, trace)
    assert [reason for reason, _ in result["stops"]] == ["memory_exhausted"]
    assert result["relief_times"] == []  # emergency does not wait for voice relief


def test_voice_is_not_unloaded_mid_utterance(guardian):
    # The guardian never yanks TTS weights while a sentence is playing.
    trace = [snap(guardian, used_gib=63.2) for _ in range(8)]
    result = run_watch(guardian, trace, voice_playing=True)
    assert result["relief_times"] == []
    # Engine protection still proceeds once strikes accumulate.
    assert [reason for reason, _ in result["stops"]] == ["system_memory"]


def test_unload_is_rate_limited_to_once_per_minute(guardian):
    # Footprint over the 55 GiB ceiling, plenty of system headroom: sustained
    # but not exhausting. Over 65 simulated seconds, at most two unloads.
    trace = [snap(guardian, used_gib=50.0, footprint_gib=56.0) for _ in range(260)]
    result = run_watch(guardian, trace)
    assert result["relief_times"]
    for first, second in zip(result["relief_times"], result["relief_times"][1:]):
        assert second - first >= guardian.VOICE_SHED_INTERVAL_SEC
    # 65 s of sustained pressure through ~260 samples produced a handful of
    # unloads, not one per sample.
    assert len(result["relief_times"]) < 5


def test_recovery_clears_the_shed_flag(guardian):
    trace = [snap(guardian, used_gib=62.0) for _ in range(5)]
    trace += [snap(guardian, used_gib=57.0) for _ in range(5)]
    result = run_watch(guardian, trace)
    assert result["pressures"][:5] == [True] * 5
    assert result["pressures"][5:] == [False] * 5
    assert result["stops"] == []


def test_idle_unload_only_arms_near_the_kill_line(guardian):
    # A long idle at 61 GiB keeps the model warm. At 62 GiB it is released
    # gracefully before the sustained-kill path can fire.
    trace = [snap(guardian, used_gib=61.0) for _ in range(8)]
    result = run_watch(guardian, trace, idle_sec=300.0)
    assert result["stops"] == []

    trace = [snap(guardian, used_gib=62.0)]
    result = run_watch(guardian, trace, idle_sec=300.0)
    assert [reason for reason, _ in result["stops"]] == ["proactive_idle_pressure"]


def test_keep_policy_blocks_the_idle_unload(guardian):
    # Rule 4 respects the watchdog's "keep" policy even at the arm line with a
    # 300 s idle: an owner who asked for the model to stay warm is not unloaded.
    trace = [snap(guardian, used_gib=62.0) for _ in range(6)]
    result = run_watch(guardian, trace, idle_sec=300.0, idle_policy="keep")
    assert result["stops"] == []


def test_in_flight_request_blocks_the_idle_unload(guardian):
    # "Idle" with a queued request in flight is not idle: the unload would
    # interrupt work the engine has already accepted.
    trace = [snap(guardian, used_gib=62.0) for _ in range(6)]
    result = run_watch(guardian, trace, idle_sec=300.0, idle_in_flight=True)
    assert result["stops"] == []


def test_busy_slot_blocks_the_idle_unload_until_it_drains(guardian):
    # A busy prompt slot blocks the proactive unload; the unload fires on the
    # first sample where the slot is free, and the trace continues past the
    # action on a now-dead engine without re-firing.
    trace = [snap(guardian, used_gib=62.0) for _ in range(8)]
    result = run_watch(guardian, trace, idle_sec=300.0,
                       slot_busy=[True] * 4 + [False] * 4)
    assert [reason for reason, _ in result["stops"]] == ["proactive_idle_pressure"]


def test_two_engines_are_never_both_running(guardian):
    # Rule 0: a second engine is stopped the moment it is sampled alongside
    # Strata, before any memory rule applies. The trace only has to last until
    # the field reality — the kill lands, the next sample is no longer dual.
    trace = [snap(guardian, used_gib=50.0, footprint_gib=46.0, dual=True)]
    trace += [snap(guardian, used_gib=50.0, footprint_gib=46.0) for _ in range(5)]
    result = run_watch(guardian, trace)
    assert result["stops"] == [("dual_engine_conflict", 1000.0)]
    assert result["targets"] == ["mtplx"]
    # Nothing else fires: 50 GiB is nowhere near the kill lines.
    assert all(reason != "system_memory" for reason, _ in result["stops"])


def test_dual_engine_rule_precedes_the_emergency_stop(guardian):
    # Zero headroom *and* a second engine: the conflict is resolved first
    # (targeted, secondary engine only); the generic kill only fires after the
    # conflict is gone and the emergency condition persists.
    trace = [snap(guardian, used_gib=63.4, dual=True),
             snap(guardian, used_gib=63.4)]
    result = run_watch(guardian, trace)
    assert [reason for reason, _ in result["stops"]] == [
        "dual_engine_conflict", "memory_exhausted"
    ]
    assert result["targets"] == ["mtplx", "all"]


def test_dual_engine_conflict_skips_the_voice_shed(guardian):
    # Rule 0 continues before write_pressure/shed_voice run: on the conflicting
    # sample the guardian fixes the conflict, it does not shed voice. The
    # targeted stop kills only MTPLX, so later samples are no longer dual and
    # the normal tiers resume: 62 GiB writes the shed flag but is not tight,
    # so no unload happens.
    trace = [snap(guardian, used_gib=62.0, dual=True) for _ in range(3)]
    result = run_watch(guardian, trace)
    assert result["relief_times"] == []
    assert [reason for reason, _ in result["stops"]] == ["dual_engine_conflict"]
    assert result["pressures"] == [True, True]  # written only after resolution


def test_swap_growth_stays_quiet_above_the_headroom_floor(guardian):
    # 512 MiB of swap growth with 2.5 GiB headroom is NOT a kill condition: the
    # swap rule requires headroom under 1 GiB, so the voice path backs off (used
    # >= 61 GiB writes shedVoice) while the engine stays resident.
    trace = [snap(guardian, used_gib=61.5, swap_growth=512 * 1024**2,
                  swap_delta=100) for _ in range(20)]
    result = run_watch(guardian, trace)
    assert result["stops"] == []
    assert result["relief_times"] == []  # nothing is tight, so no unload attempt
    assert all(result["pressures"])


def test_swap_label_wins_when_growth_accompanies_the_headroom_floor(guardian):
    # 63.2 GiB used (0.8 GiB headroom) plus 128 MiB swap growth with active
    # swapouts: the kill is attributed to "swap", not the generic system line,
    # and voice relief still precedes it. Structural note pinned here: swapping
    # requires headroom < 1 GiB, the same floor as overSystem, so swap growth can
    # label a kill but never trigger one on its own. The trace runs 60
    # samples — well past the kill — and exactly one stop must land: the
    # synthetic engine is dead after the stop, so Rule 3 cannot re-fire.
    trace = [snap(guardian, used_gib=63.2, swap_growth=128 * 1024**2,
                  swap_delta=32) for _ in range(60)]
    result = run_watch(guardian, trace)
    assert len(result["relief_times"]) == 1
    assert [reason for reason, _ in result["stops"]] == ["swap"]
    assert result["stops"][0][1] - result["relief_times"][0] >= guardian.RELIEF_GRACE_SEC


def test_unload_failure_reports_no_relief(guardian):
    # A refused connection is reported as relief unavailable, not as freed memory.
    def boom(url, payload=None):
        raise OSError("connection refused")

    original_http = guardian._http_json
    original_playing = guardian._voice_is_playing
    guardian._http_json = boom
    guardian._voice_is_playing = lambda: False
    try:
        result = guardian.shed_voice()
    finally:
        guardian._http_json = original_http
        guardian._voice_is_playing = original_playing
    assert result["freedBytes"] == 0
    assert "unavailable" in result["detail"]


def test_no_model_loaded_is_not_counted_as_relief(guardian):
    def status(url, payload=None):
        return {"models": [{"model_name": "qwen-tts", "loaded": False}]}

    original_http = guardian._http_json
    original_playing = guardian._voice_is_playing
    guardian._http_json = status
    guardian._voice_is_playing = lambda: False
    try:
        result = guardian.shed_voice()
    finally:
        guardian._http_json = original_http
        guardian._voice_is_playing = original_playing
    assert result["freedBytes"] == 0
    assert result["detail"] == "no model loaded"


def test_unload_is_rechecked_before_the_post(guardian):
    # The gate in watch() can pass, then an utterance starts before the POST.
    # shed_voice must re-check the playing flag and not touch the weights.
    posts: list[str] = []

    def fake_http(url, payload=None):
        posts.append(url)
        return {"models": [{"model_name": "qwen-tts", "loaded": True}]}

    original_http = guardian._http_json
    original_playing = guardian._voice_is_playing
    original_footprint = guardian.voicebox_footprint_bytes
    try:
        guardian._http_json = fake_http
        guardian._voice_is_playing = lambda: True
        guardian.voicebox_footprint_bytes = lambda: 3 * GIB
        result = guardian.shed_voice()
    finally:
        guardian._http_json = original_http
        guardian._voice_is_playing = original_playing
        guardian.voicebox_footprint_bytes = original_footprint
    assert result["freedBytes"] == 0
    assert "deferred" in result["detail"]
    assert posts == []  # not even the status round trip happens while a sentence plays


def test_unload_with_no_measured_freed_graces_only_once(guardian):
    # The sidecar can answer the unload POST with success before the OS has
    # actually reclaimed the pages, so `freedBytes` is 0 while the detail says
    # "unloaded". That arms the grace clock exactly once (bounded by
    # RELIEF_GRACE_SEC); if the relief never materializes the kill still fires,
    # and a true zero-headroom emergency ignores the grace entirely (rule 1).
    trace = [snap(guardian, used_gib=63.2) for _ in range(60)]
    result = run_watch(
        guardian,
        trace,
        shed_result={"freedBytes": 0, "detail": "unloaded qwen-tts-0.6B"},
    )
    assert len(result["relief_times"]) == 1
    assert any("RELIEF_PENDING" in line for line in result["logs"])
    assert result["stops"], "the kill must still fire once the grace expires"
    stop_at = result["stops"][0][1]
    assert stop_at - result["relief_times"][0] >= guardian.RELIEF_GRACE_SEC
    assert all(reason == "system_memory" for reason, _ in result["stops"])

def test_failed_unload_does_not_count_as_relief(guardian):
    # A refused connection must not arm the relief grace clock or log RELIEF;
    # the engine kill proceeds on its own schedule.
    trace = [snap(guardian, used_gib=63.2) for _ in range(8)]
    result = run_watch(
        guardian,
        trace,
        shed_result={"freedBytes": 0, "detail": "voice relief unavailable: connection refused"},
    )
    assert result["relief_times"] == []
    assert not any(line.startswith("RELIEF") for line in result["logs"])
    assert any(line.startswith("VOICE_DEFER") for line in result["logs"])
    assert [reason for reason, _ in result["stops"]] == ["system_memory"]
