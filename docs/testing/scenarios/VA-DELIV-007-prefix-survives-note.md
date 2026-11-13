# VA-DELIV-007 — A note leaves the send prefix

1. **ID:** VA-DELIV-007
2. **Checked:** 2026-11-13 23:42 UTC.
3. **Level:** LEVEL 1. No microphone. No keystrokes. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_note_leaves_the_send_prefix_held -q`
5. **Result:** Passed. The retry, failed-prefix, empty-prefix send, send-once, and failed-status flush tests still passed.
6. **Note.** `Ship the notes.` is held. `ship all done` fails to post, so `ship` is kept apart from the sentence. `Thanks.` posts `Ship the notes. Thanks.` once. `ship` stays held. The next `all done` posts `ship send prompt` once. Same on v1.
7. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
