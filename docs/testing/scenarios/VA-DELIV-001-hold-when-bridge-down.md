# VA-DELIV-001 — A dead bridge holds a non-command once

1. **ID:** VA-DELIV-001
2. **Checked:** 2026-11-13 23:02 UTC.
3. **Level:** LEVEL 1. No microphone. Handy is not executed. The focused app is not typed into. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_a_failed_status_holds_the_flush_once_and_does_not_type tests/test_wake_and_gain.py::test_a_dead_bridge_types_a_scratch_unless_focus_is_text -q`
5. **Result:** Both passed. The Handy file as a whole passed with them.
6. **Flush.** The row `Ship the notes.` gets a status GET and no transcript POST. `fallback_macos_inject` is not called. The hold is that sentence. A second dispatch of the same sentence does not copy it. When status returns, `Thanks.` is posted once as `Ship the notes. Thanks.` and the hold is cleared.
7. **Commands.** `send`, `pause`, `cancel`, and `scratch` on a dead bridge still use the old keystroke fallback. A focused text control still pastes.
8. **Live process.** Controller pid 64238 was not restarted, so it still types a non-command when status fails. OMP pid 16590 was not signaled.
