# VA-DELIV-020 — A failed v2 scratch keeps both holds

1. **ID:** VA-DELIV-020
2. **Checked:** 2026-11-14 00:58 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_v2_scratch_keeps_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The failed v2 pause, the successful scratch-with-prefixes test, and the dead-bridge command test still passed.
6. **Post down.** `Ship the notes.` and `ship please` are held. Status GET is version 2. The transcript POST returns nothing. `scratch that` does not type. Both holds stay. The visible hold is `Ship the notes. ship please`.
7. **Unchanged.** A status GET that fails still types scratch. This case is only a failed POST after a successful status GET.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
