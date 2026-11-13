# VA-DELIV-037 — A cancel row stays idle

1. **ID:** VA-DELIV-037
2. **Checked:** 2026-11-14 02:40 UTC.
3. **Level:** LEVEL 1. No microphone. Handy and the bridge are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_handy_row_during_dictation_is_dispatched_before_the_pause -q`
5. **Result:** Passed. The cancelled silence flush still passed.
6. **Row.** Dictation is open. A new history row is `cancel`. Dispatch returns `cancelled`. The state is IDLE. `handy_start_recording` is not called. The speech flag is cleared.
7. **Cue.** This slice left the pause cue in place. VA-DELIV-038 plays the cancel cue for this row. A pause row still plays the pause cue.
8. **Code.** The row branch already returns to idle for `cancelled` and starts Handy only for scratch, clear, and an ordinary chunk. No controller change.
9. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
