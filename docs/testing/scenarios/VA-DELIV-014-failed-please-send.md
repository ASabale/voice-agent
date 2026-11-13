# VA-DELIV-014 — A failed please send keeps both prefixes

1. **ID:** VA-DELIV-014
2. **Checked:** 2026-11-14 00:22 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_please_send_keeps_both_prefixes -q`
5. **Result:** Passed. The successful first post and the failed-status second-prefix test still passed.
6. **Post down.** `Ship the notes.` and `ship` are held. Status GET is ok. The transcript POST for `please all done` returns nothing. Nothing is typed. The sentence stays. The prefix becomes `ship please`. The next successful `please all done` posts `Ship the notes. ship please send prompt` once and clears both. The following one posts `please send prompt` only.
7. **Code.** The failed-send return already joined the new prefix. This slice locks that retry. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
