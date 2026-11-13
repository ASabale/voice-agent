# VA-DELIV-003 — Scratch and pause leave a held sentence

1. **ID:** VA-DELIV-003
2. **Checked:** 2026-11-13 23:18 UTC.
3. **Level:** LEVEL 1. No microphone. No keystrokes. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_scratch_and_pause_leave_a_held_sentence tests/test_wake_and_gain.py::test_a_held_sentence_is_sent_once -q`
5. **Result:** Both passed. The empty-hold v1 and v2 dispatch tests and the dead-bridge command test also passed.
6. **Aside.** With `Ship the notes.` held, v2 posts `scratch that` and `please stop` and leaves the hold. v1 posts `scratch that` and `please pause listening` and leaves the hold. A following `all done` posts `Ship the notes. send prompt` once and clears it.
7. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
