# VA-DELIV-030 — Cancel leaves the sentence and both prefixes

1. **ID:** VA-DELIV-030
2. **Checked:** 2026-11-14 01:58 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_cancel_leaves_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The successful v2 clear and the dead-bridge command test still passed.
6. **Cancel.** `Ship the notes.` and `ship please` are held. Status GET is version 2. `cancel` posts `cancel` only and does not type. Both holds stay. The next `all done` posts `Ship the notes. ship please send prompt` once and clears both.
7. **Code.** Cancel was already an aside command, and only a clear drops the holds. This slice locks that difference. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
