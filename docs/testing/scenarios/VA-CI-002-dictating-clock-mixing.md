# VA-CI-002 — Dictating-frame clock mixing: tests passed locally only by uptime luck

**Date:** 2026-11-16 04:45 UTC
**Class:** Regression gap (environment-dependent false pass)
**Result:** PASS (fixed; reproduced pre-fix under a pinned CI clock)

## Symptom
CI run 43804755039 on `f954713` failed 6 tests in `tests/test_handy_control.py`
(`test_an_older_history_read_does_not_replace_the_consumed_flush_row`, `..._repeat_a_scratched_flush_row`,
`..._repeat_a_cleared_flush_row`, `test_a_newer_history_row_is_dispatched_once_after_the_flush`,
`..._after_a_scratch_flush`, `..._after_a_clear_flush`) with
`AssertionError: handy_cancel`, raised at `bin/omp-voice-controller:3888` (the DICTATING idle-timeout branch),
while the identical suite passed locally (314/314).

## Root cause
`MicState.handle_dictating_frame` receives the frame timestamp as `now` but, on the "continue dictating"
paths (after an appended/scratched/cleared flush), reset `chunk_started_at = time.monotonic()` — a *different
clock* than the test's synthetic `now = 100.0`. On CI the runner's `time.monotonic()` is the fresh VM uptime
(≈85 s when pytest started), so the second synthetic frame at `now = 100.1` satisfied
`now - chunk_started_at >= 15.0`, fired "No speech for 15s in DICTATING -> cancelling Handy", and hit the
stub that throws `AssertionError("handy_cancel")`. On this machine `time.monotonic()` is days of uptime
(millions of seconds), so `100.1 - 4.7e6` is negative and the timeout never fires: the tests passed only
because of the machine's uptime, not because the logic was right.

## Fix
All three chunk-restart resets inside `handle_dictating_frame` now use the frame's `now` (lines 3745, 3856,
3878): `chunk_started_at = now`, `last_speech_at = now`, `cooldown_until = now + 0.25`. In production the
loop passes `now = time.monotonic()` per frame, so behavior is unchanged there; the handler no longer mixes
clocks within one frame. Timing measurements (`flush_mono`, `asr_s`, `dispatch_s`) keep real monotonic
deltas — they are measured inside one call, not compared to the synthetic timeline.

## Verification
1. `~/.local/share/omp-voice/venv/bin/python -m pytest tests/ -q` → 314 passed.
2. CI-clock reproduction: a pytest plugin pinning `time.monotonic` to 85.0 (`/tmp/ci_clock_plugin.py`):
   - pre-fix controller (`f954713`): 6 failed, 21 passed — exact CI failure set.
   - post-fix controller: 27 passed.
3. CI re-run on the fix commit observed via `gh run view` (recorded in the checkpoint).

## Lesson
Any handler that takes a caller-supplied timestamp must use that timestamp for all state it later compares
against it. A test that passes only because the host clock is far from the synthetic timeline is a latent
flake, not a pass.
