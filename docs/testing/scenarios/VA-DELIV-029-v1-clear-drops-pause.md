# VA-DELIV-029 — A v1 clear drops the saved pause line

1. **ID:** VA-DELIV-029
2. **Checked:** 2026-11-14 01:52 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_v1_clear_drops_the_pause_line_before_the_next_send -q`
5. **Result:** Passed. The v2 clear-drops-pause test and the failed v1 clear still passed.
6. **Order.** `Ship the notes.` and `ship please` are held. `please stop` posts `please pause listening` and saves `please`. `clear draft` posts `clear draft` only, clears both holds, and clears the saved pause. The next `all done` posts `send prompt` only. Nothing is typed.
7. **Code.** A successful clear already dropped the pause line on both bridge versions. This slice locks the v1 order. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
