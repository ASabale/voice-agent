# VA-DELIV-045 — An older history read does not repeat a clear

1. **ID:** VA-DELIV-045
2. **Checked:** 2026-11-14 03:28 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_an_older_history_read_does_not_repeat_a_cleared_flush_row -q`
5. **Result:** Passed. The scratch flush and the appended flush history tests still passed.
6. **Clear.** The previous id is 3. The flush consumes row 8, `clear draft`. Dispatch returns `cleared`. The follow-up read returns id 0. `last_history_id` stays 8. Handy starts once. The state stays DICTATING. The next frame sees id 8 and does not dispatch `clear draft` again.
7. **Code.** Clear uses the same guard as scratch. This slice locks the clear result. VA-DELIV-046 dispatches a newer row once instead of skipping it.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
