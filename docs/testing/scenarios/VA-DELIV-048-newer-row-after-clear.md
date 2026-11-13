# VA-DELIV-048 — A newer row after a clear is dispatched once

1. **ID:** VA-DELIV-048
2. **Checked:** 2026-11-14 03:46 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_a_newer_history_row_is_dispatched_once_after_a_clear_flush -q`
5. **Result:** Passed. The scratch newer-row test and the older clear history test still passed.
6. **Order.** The previous id is 3. The flush consumes row 8, `clear draft`, and returns `cleared`. The id stays 8. Dictation stays open. The next frame dispatches row 9, `Next line.`, once. The id becomes 9. A third frame does not dispatch it again.
7. **Code.** The clear branch already stopped marking a later id as seen. This slice locks that result. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
