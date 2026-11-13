# VA-DELIV-046 — A newer row after a flush is dispatched once

1. **ID:** VA-DELIV-046
2. **Checked:** 2026-11-14 03:34 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_a_newer_history_row_is_dispatched_once_after_the_flush -q`
5. **Result:** Passed. The clear, scratch, and append history tests still passed. The appended status test and the held flush still passed.
6. **Order.** The previous id is 3. The flush consumes row 8, `Thanks.`, and leaves that id. The next frame sees row 9, `Next line.`, and dispatches it once. The id becomes 9. A third frame does not dispatch it again. The state stays DICTATING.
7. **Code.** The flush no longer marks a later history id as seen. The next frame's live-row check delivers it. The scratch and clear branches lost the same skip and are not locked for a newer row.
8. **Live process.** Controller pid 64238 was not restarted. It can still skip the later row. OMP pid 16590 was not signaled.
