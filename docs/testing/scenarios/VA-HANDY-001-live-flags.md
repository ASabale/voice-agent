# VA-HANDY-001 — Live Handy flags, process stubbed

1. **ID:** VA-HANDY-001
2. **Checked:** 2026-11-13 22:15 UTC.
3. **Level:** LEVEL 1. The Handy binary is not executed. `history.db` is not opened. Not live dictation. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py -q`
5. **Result:** 5 passed.
6. **Flags.** With the app treated as running, cancel is `[handy, --cancel]`. Stop is one `--toggle-transcription`. A fresh start is that toggle and not a cancel. A restart is cancel, then the toggle. With the app treated as stopped, cancel, stop, and start do not call the binary. The only launch is `handy_start_recording(allow_launch=True, fresh=True)`.
7. **File mode.** A wake with `OMP_VOICE_HANDY=transcribe-file` enters `DICTATING` and does not start a thread or call Handy. `silence_speech`, the cue, the history read, and `write_status` are stubbed in that test.
8. **Left alone.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled. The microphone was not opened.
