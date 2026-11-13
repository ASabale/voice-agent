# VA-DELIV-044 — An older history read does not repeat a scratch

1. **ID:** VA-DELIV-044
2. **Checked:** 2026-11-14 03:22 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_an_older_history_read_does_not_repeat_a_scratched_flush_row -q`
5. **Result:** Passed. The appended flush history test and the appended status test still passed.
6. **Scratch.** The previous id is 3. The flush consumes row 8, `scratch that`. Dispatch returns `scratched`. The follow-up read returns id 0. `last_history_id` stays 8. Handy starts once. The state stays DICTATING. The next frame sees id 8 and does not dispatch `scratch that` again.
7. **Code.** The scratch branch already ignored an older id. This slice locks that result. VA-DELIV-045 locks the clear result. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
