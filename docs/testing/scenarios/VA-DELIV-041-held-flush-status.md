# VA-DELIV-041 — A held flush records held

1. **ID:** VA-DELIV-041
2. **Checked:** 2026-11-14 03:04 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_a_held_send_flush_stays_dictating_and_keeps_both_holds -q`
5. **Result:** Passed. The cancelled flush and the sent flush still passed.
6. **Status.** Dictation has been quiet for 10 seconds. Dispatch returns `held`. The status write is `DICTATING` with `last_action` `held`. The state stays DICTATING. Both holds stay. Nothing is typed.
7. **Code.** The flush used to store `appended` for every result in this branch. It now stores the dispatch action. An ordinary append still stores `appended`. A sent flush still returns to IDLE.
8. **Live process.** Controller pid 64238 was not restarted. It still records `appended` for this flush. OMP pid 16590 was not signaled.
