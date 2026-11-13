# VA-DELIV-008 — A dead status does not press Enter over a held prefix

1. **ID:** VA-DELIV-008
2. **Checked:** 2026-11-13 23:48 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_dead_status_does_not_press_enter_while_a_prefix_is_held -q`
5. **Result:** Passed. The dead-bridge command test, the note-leaves-prefix test, and the empty-prefix failed send still passed.
6. **Status down.** `Ship the notes.` and `ship` are held. Status GET returns nothing. `all done` does not call the keystroke fallback. Both stays held. After the hold is cleared, `all done` still calls the fallback with an empty prefix, which is the Enter key.
7. **Unchanged.** `ship all done` on a dead bridge, with no prefix held, still types `ship` and presses Enter.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
