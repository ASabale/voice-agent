# VA-DELIV-027 — A failed clear keeps the pause line

1. **ID:** VA-DELIV-027
2. **Checked:** 2026-11-14 01:40 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_clear_keeps_the_pause_line -q`
5. **Result:** Passed. The successful clear-drops-pause test and the failed v2 clear still passed.
6. **Failed clear.** `Ship the notes.` and `ship please` are held. `please stop` posts `please stop` and saves `please`. The `clear draft` POST returns nothing. Nothing is typed. `please` stays saved. Both holds stay. The next `all done` posts `Ship the notes. ship please send prompt` once and clears the pause line and both holds.
7. **Code.** The failed clear already returned before the pause line was dropped. This slice locks that order. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
