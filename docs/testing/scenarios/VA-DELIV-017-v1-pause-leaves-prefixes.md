# VA-DELIV-017 — A v1 pause leaves the sentence and both prefixes

1. **ID:** VA-DELIV-017
2. **Checked:** 2026-11-14 00:40 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_v1_pause_leaves_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The v2 pause-with-prefixes test and the v1 pause rewrite test still passed.
6. **v1 pause.** `Ship the notes.` and `ship please` are held. Status GET is version 1. `please stop` posts `please pause listening` only and does not type. Both holds stay. The next `all done` posts `Ship the notes. ship please send prompt` once and clears both. `please` is not copied a second time.
7. **Code.** The v1 pause post already returned before the hold was cleared, and the stored prefix already ended in `please`. This slice locks that case. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
