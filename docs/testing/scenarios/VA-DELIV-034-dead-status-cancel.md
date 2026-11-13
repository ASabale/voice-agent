# VA-DELIV-034 — A dead status does not type cancel

1. **ID:** VA-DELIV-034
2. **Checked:** 2026-11-14 02:22 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_dead_status_does_not_type_cancel_while_both_holds_are_set -q`
5. **Result:** Passed. The empty-hold dead-bridge test and the successful v1 cancel still passed.
6. **Status down.** `Ship the notes.` and `ship please` are held. The status GET returns nothing. `cancel` does not type. Both holds stay. The return is `cancelled`.
7. **Unchanged.** With nothing held, a dead status still types scratch, `ship all done`, and pause, and still does not type cancel. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
