# VA-DELIV-015 — Scratch leaves the sentence and both prefixes

1. **ID:** VA-DELIV-015
2. **Checked:** 2026-11-14 00:28 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_scratch_leaves_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The sentence-only scratch/pause test and the failed please-send test still passed.
6. **Scratch.** `Ship the notes.` and `ship please` are held. Status GET is ok. `scratch that` posts `scratch that` only and does not type. Both holds stay. The next `all done` posts `Ship the notes. ship please send prompt` once and clears both.
7. **Code.** Scratch was already an aside command. This slice locks it with both prefixes. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
