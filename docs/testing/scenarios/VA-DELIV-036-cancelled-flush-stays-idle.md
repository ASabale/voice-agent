# VA-DELIV-036 — A cancelled flush stays idle

1. **ID:** VA-DELIV-036
2. **Checked:** 2026-11-14 02:34 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_a_cancelled_flush_returns_to_idle_without_starting_handy -q`
5. **Result:** Passed. The sent flush and the live-row dispatch test still passed.
6. **Flush.** Dictation has been quiet for 10 seconds. Handy returns the row `cancel`. Dispatch returns `cancelled`. The stop toggle runs once. The cancel cue plays. The state is IDLE. `handy_start_recording` is not called.
7. **Code.** The flush already returns to idle for `cancelled` and starts Handy only for scratch, clear, and an ordinary chunk. This slice locks the cancel result. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
