# VA-DELIV-002 — A held sentence is sent once

1. **ID:** VA-DELIV-002
2. **Checked:** 2026-11-13 23:10 UTC.
3. **Level:** LEVEL 1. No microphone. No keystrokes. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_held_sentence_is_sent_once -q`
5. **Result:** Passed. The empty-hold v1 and v2 dispatch tests and the VA-DELIV-001 flush still passed.
6. **Send.** With `Ship the notes.` held, `all done` posts `Ship the notes. send prompt` once on a v2 bridge and once on a v1 bridge. The hold is cleared. A second `all done` posts `send prompt` only.
7. **Live process.** Controller pid 64238 was not restarted, so it does not attach the hold yet. OMP pid 16590 was not signaled.
