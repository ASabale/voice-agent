"""VA-SOAK-006: the soak verdict is computed from measured deltas, not
lifetime absolutes. These pin the gate semantics that the first run exposed:
mic counters are controller-lifetime cumulative, RSS compares median to median,
and a human speaking during the window contaminates the run instead of
failing the controller."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_long_soak_probe as probe  # noqa: E402


def healthy_evidence() -> dict:
    return {
        "cycles": [{"turns_played": probe.TURNS} for _ in range(probe.CYCLES)],
        "wake_lines_total": 0,
        "human_transcript_lines": 0,
        "speech_failed_total": 0,
        "final_status": {"render_connected": False, "state": "IDLE"},
        "mic_dropped_delta": 0,
        "mic_invalid_delta": 0,
        "controller_alive": True,
        "slot_dir_count_final": 1,
        "rss_baseline_median_mb": 180.0,
        "rss_post_run_median_mb": 195.0,
        "rss_after_cycle_max_mb": 260.0,
        "rss_cycle_medians_mb": [180.0] * probe.CYCLES,
        "voicebox_footprint_baseline_mb": 5600,
        "voicebox_footprints_mb": [5650, 5700],
        "controller_log_bytes_at_start": 5_000_000,
        "controller_log_bytes_end": 6_000_000,
    }


def test_healthy_run_passes():
    assert probe.evaluate(healthy_evidence()) == "PASS"


def test_absolute_mic_counts_do_not_fail_a_healthy_delta():
    """The old gate read the lifetime counter; a controller with 7 lifetime
    drops and zero drops during the soak must pass."""
    ev = healthy_evidence()
    ev["final_status"]["mic_dropped"] = 7
    ev["final_status"]["mic_invalid"] = 3
    assert probe.evaluate(ev) == "PASS"
    ev["mic_dropped_delta"] = 1
    assert probe.evaluate(ev) == "FAIL"


def test_human_speech_contaminates_rather_than_fails():
    ev = healthy_evidence()
    ev["wake_lines_total"] = 2
    ev["human_transcript_lines"] = 1
    assert probe.evaluate(ev) == "CONTAMINATED"
    ev["human_transcript_lines"] = 0
    assert probe.evaluate(ev) == "FAIL"


def test_rss_gate_compares_medians_within_settle_limit():
    ev = healthy_evidence()
    ev["rss_post_run_median_mb"] = 180.0 + probe.RSS_SETTLE_LIMIT_MB
    assert probe.evaluate(ev) == "PASS"
    ev["rss_post_run_median_mb"] = 180.0 + probe.RSS_SETTLE_LIMIT_MB + 0.1
    assert probe.evaluate(ev) == "FAIL"
    ev["rss_post_run_median_mb"] = 195.0
    ev["rss_after_cycle_max_mb"] = 180.0 + probe.RSS_ENVELOPE_LIMIT_MB + 1
    assert probe.evaluate(ev) == "FAIL"


def test_missing_rss_baseline_is_not_silently_a_pass():
    ev = healthy_evidence()
    ev["rss_baseline_median_mb"] = None
    assert probe.evaluate(ev) == "FAIL"


def test_rising_cycle_floor_fails_as_drift():
    """Churn oscillates; a leak raises the floor every cycle."""
    ev = healthy_evidence()
    ev["rss_cycle_medians_mb"] = [180 + i * probe.RSS_SETTLE_LIMIT_MB for i in range(probe.CYCLES)]
    ev["rss_post_run_median_mb"] = ev["rss_cycle_medians_mb"][-1]
    assert probe.evaluate(ev) == "FAIL"


def test_oscillating_cycle_floor_does_not_fail_as_drift():
    ev = healthy_evidence()
    ev["rss_cycle_medians_mb"] = [180.0, 260.0, 190.0, 270.0, 185.0, 255.0]
    assert probe.evaluate(ev) == "PASS"
