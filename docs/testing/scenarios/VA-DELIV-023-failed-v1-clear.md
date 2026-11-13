# VA-DELIV-023 — A failed v1 clear keeps both holds

1. **ID:** VA-DELIV-023
2. **Checked:** 2026-11-14 01:16 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_v1_clear_keeps_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The failed v2 clear, the failed v1 scratch, and the dead-bridge command test still passed.
6. **Post down.** `Ship the notes.` and `ship please` are held. Status GET is version 1. The transcript POST returns nothing. `clear draft` does not type. Both holds stay. The visible hold is `Ship the notes. ship please`.
7. **Unchanged.** A status GET that fails still types a non-command. This case is only a failed POST after a successful status GET.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
