# VA-DELIV-040 — A held send flush stays dictating

1. **ID:** VA-DELIV-040
2. **Checked:** 2026-11-14 02:58 UTC.
3. **Level:** LEVEL 1. No microphone. Handy, the injector, and history.db are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py::test_a_held_send_flush_stays_dictating_and_keeps_both_holds -q`
5. **Result:** Passed. The cancelled flush and the held send row still passed.
6. **Flush.** `Ship the notes.` and `ship please` are held. Dictation has been quiet for 10 seconds. Handy returns `ship all done`. Dispatch returns `held`. The state stays DICTATING. The stop toggle runs once. Handy then starts once. Nothing is typed. Both holds stay.
7. **Status.** This slice left `last_action` as `appended`. VA-DELIV-041 records `held`.
8. **Code.** A flush result other than send, pause, scratch, clear, or cancel already stayed in dictation and started Handy once. No controller change.
9. **Live process.** Controller pid 64238 was not restarted. OMP pid 16590 was not signaled.
