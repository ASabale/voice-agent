# VA-DELIV-039 — A held send row stays dictating

1. **ID:** VA-DELIV-039
2. **Checked:** 2026-11-14 02:52 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and the bridge are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_held_send_row_stays_dictating_and_keeps_both_holds -q`
5. **Result:** Passed. The cancel, pause, scratch, and send rows still passed.
6. **Row.** `Ship the notes.` and `ship please` are held. Dictation is open. The new row is `ship all done`. Dispatch returns `held`. The state stays DICTATING. Handy starts once. Nothing is typed. Both holds stay.
7. **Code.** A result other than send, pause, or cancel already stayed in dictation and started Handy once. This slice locks the failed-send result. No controller change.
8. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
