# VA-DELIV-042 — An appended flush records appended

1. **ID:** VA-DELIV-042
2. **Checked:** 2026-11-14 03:10 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_an_appended_flush_records_appended_and_stays_dictating -q`
5. **Result:** Passed. The held flush and the cancelled flush still passed.
6. **Flush.** Dictation has been quiet for 10 seconds. Handy returns `Thanks.`. Dispatch returns `appended`. The state stays DICTATING. The status write is `last_action` `appended`. The stop toggle runs once. Handy starts once. Nothing is typed.
7. **Code.** The flush already stores the dispatch action. An append stays `appended`. A held result stays `held`. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
