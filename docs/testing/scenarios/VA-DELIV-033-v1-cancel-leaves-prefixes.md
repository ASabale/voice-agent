# VA-DELIV-033 — A v1 cancel leaves the sentence and both prefixes

1. **ID:** VA-DELIV-033
2. **Checked:** 2026-11-14 02:16 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_v1_cancel_leaves_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The v2 cancel, the failed v1 cancel, and the successful v1 clear still passed.
6. **Cancel.** `Ship the notes.` and `ship please` are held. Status GET is version 1. `cancel` posts `cancel` only and does not type. Both holds stay. The next `all done` posts `Ship the notes. ship please send prompt` once and clears both.
7. **Code.** Cancel was already an aside command, and only a clear drops the holds. This slice locks the v1 success path. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
