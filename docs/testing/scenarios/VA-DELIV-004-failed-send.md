# VA-DELIV-004 — A failed send keeps the held sentence

1. **ID:** VA-DELIV-004
2. **Checked:** 2026-11-13 23:24 UTC.
3. **Level:** LEVEL 1. No microphone. No keystrokes. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_send_keeps_the_hold -q`
5. **Result:** Passed. The send-once, scratch/pause, and dead-bridge tests still passed.
6. **Failed post.** Status is ok. The transcript POST returns nothing. `all done` does not type. `Ship the notes.` stays held. A later successful POST of `all done` sends `Ship the notes. send prompt` once. Same on v1 and v2.
7. **Dead bridge.** A status GET that fails still keystrokes a send. This case is only a failed POST after a successful status GET.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
