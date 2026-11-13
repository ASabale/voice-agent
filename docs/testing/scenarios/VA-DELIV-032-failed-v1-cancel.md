# VA-DELIV-032 — A failed v1 cancel keeps both holds

1. **ID:** VA-DELIV-032
2. **Checked:** 2026-11-14 02:10 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_v1_cancel_keeps_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The failed v2 cancel, the failed v1 scratch, and the dead-bridge command test still passed.
6. **Post down.** `Ship the notes.` and `ship please` are held. Status GET is version 1. The transcript POST returns nothing. `cancel` does not type. Both holds stay. The visible hold is `Ship the notes. ship please`.
7. **Unchanged.** A status GET that fails still returns cancelled and does not type. A failed v1 scratch still keeps both holds.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
