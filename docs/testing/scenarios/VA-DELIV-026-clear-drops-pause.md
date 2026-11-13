# VA-DELIV-026 — A clear drops the saved pause line

1. **ID:** VA-DELIV-026
2. **Checked:** 2026-11-14 01:34 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_clear_drops_the_pause_line_before_the_next_send -q`
5. **Result:** Passed. The successful v2 clear, the pause-with-prefixes test, and the failed v2 clear still passed.
6. **Order.** `Ship the notes.` and `ship please` are held. `please stop` posts `please stop` and saves `please`. `clear draft` posts `clear draft` only, clears both holds, and clears the saved pause. The next `all done` posts `send prompt` only. Nothing is typed.
7. **Unchanged.** A pause that is not followed by a clear still leaves the send prefix for the next send. A failed clear still keeps the holds.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
