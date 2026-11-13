# VA-DELIV-006 — A retried send posts its prefix once

1. **ID:** VA-DELIV-006
2. **Checked:** 2026-11-13 23:36 UTC.
3. **Level:** LEVEL 1. No microphone. No keystrokes. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_retried_send_posts_the_prefix_once -q`
5. **Result:** Passed. The failed-prefix test, the empty-prefix failed send, the send-once test, and the failed-status flush still passed.
6. **Retry.** `Ship the notes.` is held. `ship all done` fails to post, so the hold is `Ship the notes. ship`. The next `ship all done` posts `Ship the notes. ship send prompt` once and clears the hold. Another `ship all done` posts `ship send prompt` only. Same on v1.
7. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
