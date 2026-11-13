# VA-TTS-008 — A non-stop transcript does not resume the clip

1. **ID:** VA-TTS-008
2. **Checked:** 2026-11-14 04:10 UTC.
3. **Level:** LEVEL 1. No microphone. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_wake_and_gain.py::test_a_non_stop_hearing_does_not_resume_the_clip tests/test_wake_and_gain.py::test_apply_whisper_stops_a_barge_and_does_not_open_handy tests/test_barge_fixture.py::test_stop_fixture_is_whispered_before_playback_can_resume -q`
5. **Result:** Passed.
6. **Transcript.** Playback is active and a barge hold is open. Whisper hears `Thank you.` The hold and the waiting flag are cleared. `resume_tts_clips` is not called. `pause_tts_clips` and `stop_playback` are not called. Playback stays active.
7. **Unchanged.** `Stop.` and `Hold on a second.` still call `stop_playback`. A sentence that merely ends in stop does not.
8. **Live process.** Controller pid 64238 was not restarted. It still resumes after a non-stop hearing. OMP pid 16590 was not reloaded.
