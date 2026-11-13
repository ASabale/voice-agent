# VA-DELIV-011 — A failed recovered post keeps the prefix

1. **ID:** VA-DELIV-011
2. **Checked:** 2026-11-14 00:04 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_recovered_post_keeps_the_held_prefix -q`
5. **Result:** Passed. The recovered-status test and the empty-prefix failed send still passed.
6. **Post down.** `Ship the notes.` and `ship` are held. Status GET is ok. The transcript POST returns nothing. `all done` does not type. Both stay held. The next successful POST sends `Ship the notes. ship send prompt` once and clears both. The following `all done` posts `send prompt` only.
7. **Code.** The failed-send return already kept the sentence and the prefix. This slice locks that retry. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
