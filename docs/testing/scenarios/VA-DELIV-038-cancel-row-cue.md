# VA-DELIV-038 — A cancel row plays the cancel cue

1. **ID:** VA-DELIV-038
2. **Checked:** 2026-11-14 02:46 UTC.
3. **Level:** LEVEL 1. No microphone. Handy and the bridge are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_handy_row_during_dictation_is_dispatched_before_the_pause -q`
5. **Result:** Passed. The cancelled silence flush still passed.
6. **Cue.** Dictation is open. A new row `cancel` returns `cancelled`. The last cue is the cancel cue. The state is IDLE. Handy is not started. A pause row still ends on the pause cue. A scratch row still starts Handy.
7. **Code.** The row branch used the pause cue for every result that was not a send. Cancel now uses the same cue as the silence flush.
8. **Live process.** Controller pid 64238 was not restarted. It still plays the pause cue for this row. OMP pid 16590 was not signaled.
