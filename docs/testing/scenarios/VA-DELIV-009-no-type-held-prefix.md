# VA-DELIV-009 — A dead status does not type a held prefix

1. **ID:** VA-DELIV-009
2. **Checked:** 2026-11-13 23:54 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_dead_status_does_not_type_a_held_send_prefix -q`
5. **Result:** Passed. The empty-command dead-status test and the dead-bridge command test still passed.
6. **Status down.** `Ship the notes.` and `ship` are held. Status GET returns nothing. `ship all done` does not call the keystroke fallback. A second failure does not copy `ship`. After the hold is cleared, `ship all done` still types `ship` and presses Enter.
7. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
