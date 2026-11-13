# VA-HANDY-005 — A wake during the cancel cooldown starts one recording

1. **ID:** VA-HANDY-005
2. **Checked:** 2026-11-13 22:57 UTC.
3. **Level:** LEVEL 1. Handy is not executed. The microphone is not opened. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_handy_control.py -q`
5. **Result:** 12 passed in that file. The idle-timeout regression in `tests/test_wake_and_gain.py` also passed.
6. **What was wrong.** `transition_to_idle` after `cancel that` sets a 0.6 s cooldown. `handle_captured_frame` returned before the idle loop, so a wake score in that window was discarded.
7. **What it does now.** The cooldown still skips idle speech, so the tail of the cancel is not a new utterance. A wake score at or above the threshold calls `enter_dictating`. The dismiss block still wins. A score of 0.1 stays `IDLE`. A score of 0.91 adds one `--toggle-transcription` and no `--cancel`.
8. **Live process.** Controller pid 64238 was not restarted, so it still drops that wake. OMP pid 16590 was not signaled.
