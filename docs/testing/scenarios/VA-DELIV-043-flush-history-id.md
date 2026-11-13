# VA-DELIV-043 — An older history read keeps the consumed flush row

1. **ID:** VA-DELIV-043
2. **Checked:** 2026-11-14 03:16 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_an_older_history_read_does_not_replace_the_consumed_flush_row -q`
5. **Result:** Passed. The appended flush, the held flush, and the cancelled flush still passed.
6. **Row.** The previous id is 3. The flush consumes row 8, `Thanks.`. The follow-up read returns id 0. `last_history_id` stays 8. The next frame sees id 8 and does not dispatch `Thanks.` again. The state stays DICTATING.
7. **Code.** The flush does not replace the consumed id with an older read. VA-DELIV-044 locks the scratch branch. VA-DELIV-046 dispatches a newer row once.
8. **Live process.** Controller pid 64238 was not restarted. It can still replace the consumed id and repeat the row. OMP pid 16590 was not signaled.
