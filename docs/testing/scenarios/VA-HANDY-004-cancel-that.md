# VA-HANDY-004 — Spoken cancel does not submit the words

1. **ID:** VA-HANDY-004
2. **Checked:** 2026-11-13 22:45 UTC.
3. **Level:** LEVEL 1. Handy is not executed. `history.db` is not opened. Not a recording. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py -q`
5. **Result:** 10 passed. VA-HANDY-001 through VA-HANDY-003 stay in that file.
6. **Flush.** A pause whose row is `cancel that` calls `handy --toggle-transcription` once. The only transcript POST is `scratch that` for the partial `Ship the notes.` A status GET is not a submit. The outcome is `cancelled`. The state is `IDLE`, and Handy is not started again.
7. **Next wake.** One more `--toggle-transcription`. No `--cancel`. The state is `DICTATING`.
8. **Left alone.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled. The microphone was not opened.
