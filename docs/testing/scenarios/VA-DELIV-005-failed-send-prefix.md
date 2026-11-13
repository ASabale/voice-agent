# VA-DELIV-005 — A failed send keeps its prefix

1. **ID:** VA-DELIV-005
2. **Checked:** 2026-11-13 23:30 UTC.
3. **Level:** LEVEL 1. No microphone. No keystrokes. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_send_keeps_the_prefix -q`
5. **Result:** Passed. The empty-prefix failed send, the send-once test, and the dead-bridge keystroke test still passed.
6. **Prefix.** Status is ok. The transcript POST returns nothing. `ship all done` does not type. The hold becomes `Ship the notes. ship`. A second failure does not copy `ship`. The words `send prompt` are not stored. A later successful `all done` posts `Ship the notes. ship send prompt` once. Same on v1 and v2.
7. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
