# VA-DELIV-012 — A second prefix stays with the held send

1. **ID:** VA-DELIV-012
2. **Checked:** 2026-11-14 00:10 UTC.
3. **Level:** LEVEL 1. No microphone. The injector is stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_second_prefix_stays_with_the_held_send -q`
5. **Result:** Passed. The dead-status prefix test and the failed recovered post still passed.
6. **Second prefix.** `Ship the notes.` and `ship` are held. Status GET returns nothing. `please all done` does not type. The prefix becomes `ship please`. A second failure does not copy `please`. Status then returns. `all done` posts `Ship the notes. ship please send prompt` once and clears both. The next `all done` posts `send prompt` only.
7. **Code.** The prefix join already kept both word groups. This slice locks that case. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
