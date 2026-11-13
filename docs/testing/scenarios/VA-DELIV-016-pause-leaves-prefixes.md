# VA-DELIV-016 — Pause leaves the sentence and both prefixes

1. **ID:** VA-DELIV-016
2. **Checked:** 2026-11-14 00:34 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_pause_leaves_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The scratch-with-prefixes test and the sentence-only scratch/pause test still passed.
6. **Pause.** `Ship the notes.` and `ship please` are held. Status GET is ok. `please stop` posts `please stop` only and does not type. Both holds stay. The next `all done` posts `Ship the notes. ship please send prompt` once and clears both. `please` is not copied a second time.
7. **Code.** Pause was already an aside command, and the stored prefix already ended in `please`. This slice locks that case. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
