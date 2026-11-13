# VA-HANDY-002 — One flush, one stop, one submit

1. **ID:** VA-HANDY-002
2. **Checked:** 2026-11-13 22:25 UTC.
3. **Level:** LEVEL 1. Handy is not executed. `history.db` is not opened. Not a recording. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py -q`
5. **Result:** 7 passed. The five VA-HANDY-001 flag tests are in the same file.
6. **Flush.** One silent dictation frame after 10 seconds calls `handy --toggle-transcription` once. The stubbed history row `Ship the notes.` is submitted once, punctuation included. The state returns to `IDLE`. Cancel, a second toggle, and `handy_start_recording` are not called. `sqlite3.connect` raises if the database is opened.
7. **Partial.** The same partial text is posted to the bridge once. A repeat does not post again and does not call `dispatch_transcript`.
8. **Left alone.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled. The microphone was not opened.
