# VA-DELIV-010 — A recovered status sends the held prefix once

1. **ID:** VA-DELIV-010
2. **Checked:** 2026-11-13 23:58 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_recovered_status_sends_the_held_prefix_once -q`
5. **Result:** Passed. The dead-status prefix test and the note-leaves-prefix test still passed.
6. **Recovery.** `Ship the notes.` and `ship` are held. `ship all done` gets no status and does not type. Status then returns. `all done` posts `Ship the notes. ship send prompt` once and clears both. The next `all done` posts `send prompt` only.
7. **Code.** The post was already built by the held-prefix path. This slice locks that recovery. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
