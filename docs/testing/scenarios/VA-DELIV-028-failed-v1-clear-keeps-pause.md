# VA-DELIV-028 — A failed v1 clear keeps the pause line

1. **ID:** VA-DELIV-028
2. **Checked:** 2026-11-14 01:46 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_v1_clear_keeps_the_pause_line -q`
5. **Result:** Passed. The v2 failed-clear pause test and the v1 pause-with-prefixes test still passed.
6. **Failed clear.** `Ship the notes.` and `ship please` are held. `please stop` posts `please pause listening` and saves `please`. The `clear draft` POST returns nothing. Nothing is typed. `please` stays saved. Both holds stay. The next `all done` posts `Ship the notes. ship please send prompt` once and clears the pause line and both holds.
7. **Code.** The failed v1 clear already returned before the pause line was dropped. This slice locks that order. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
