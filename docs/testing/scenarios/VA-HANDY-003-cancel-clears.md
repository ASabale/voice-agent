# VA-HANDY-003 — Cancel clears the partial, then one new recording

1. **ID:** VA-HANDY-003
2. **Checked:** 2026-11-13 22:35 UTC.
3. **Level:** LEVEL 1. Handy is not executed. `history.db` is not opened. Not a recording. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py -q`
5. **Result:** 9 passed. VA-HANDY-001 and VA-HANDY-002 stay in that file.
6. **Cancel.** Fifteen seconds with no speech scratches the partial (`scratch that` once), then calls `handy --cancel` once. The local partial and its bridge base are empty. The state is `IDLE`. The transcript is not submitted.
7. **Next wake.** `enter_dictating` adds one `--toggle-transcription` and does not cancel again. The state is `DICTATING`.
8. **File mode.** The same timeout does not call Handy and does not touch the bridge.
9. **Code.** The idle timeout now calls `retract_partial` before `handy_cancel`. Controller pid 64238 was not restarted, so the running process still skips that scratch.
10. **Left alone.** OMP pid 16590 was not signaled. The microphone was not opened.
