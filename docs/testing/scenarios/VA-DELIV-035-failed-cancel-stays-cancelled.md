# VA-DELIV-035 — A failed cancel post stays cancelled

1. **ID:** VA-DELIV-035
2. **Checked:** 2026-11-14 02:28 UTC.
3. **Level:** LEVEL 1. No microphone. The injector and osascript are stubbed. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_failed_v2_cancel_keeps_the_sentence_and_both_prefixes tests/test_wake_and_gain.py::test_a_failed_v1_cancel_keeps_the_sentence_and_both_prefixes -q`
5. **Result:** Passed. The failed scratch, the dead-status cancel, and both successful cancel paths still passed.
6. **Why.** A return of `held` is an ordinary chunk. The flush path then starts Handy again. Cancel is the path that returns to idle and does not restart Handy.
7. **Post down.** On version 2 and version 1, the POST returns nothing. The result is `cancelled`, the draft is `Ship the notes. ship please`, and the stripped command is `cancel`. Nothing is typed. Both holds stay.
8. **Unchanged.** A failed scratch still returns `held`. A failed status GET still returns `cancelled` and does not type. A successful cancel still posts `cancel` and leaves both holds.
9. **Live process.** Controller pid 64238 was not restarted. It still returns `held` for this failure until restart. OMP pid 16590 was not signaled.
