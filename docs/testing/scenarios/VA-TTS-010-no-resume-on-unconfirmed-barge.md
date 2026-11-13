# VA-TTS-010 — An unconfirmed barge does not resume the clip

1. **ID:** VA-TTS-010
2. **Checked:** 2026-11-13 23:27 UTC.
3. **Level:** LEVEL 1. No microphone. No audio. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_an_unconfirmed_barge_does_not_resume_the_clip tests/test_wake_and_gain.py::test_ending_playback_drops_a_barge_hold_and_resumes_the_clip tests/test_wake_and_gain.py::test_two_quiet_frames_release_a_barge_hold_while_playback_continues tests/test_wake_and_gain.py::test_a_non_stop_hearing_does_not_resume_the_clip -q`
5. **Result:** Passed. 4 tests, 0 failed.
6. **Change.** The empty hold, the skipped Whisper job, and the rejected clip no longer call `resume_tts_clips`. Each still clears the hold. The call that runs after `tts_active` has become false stays, and its test still sees one resume.
7. **Live process.** Controller pid 64238 was not restarted. It still resumes on those three paths. OMP pid 16590 was not reloaded.
