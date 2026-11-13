# VA-TTS-007 — A hearing does not pause the clip

1. **ID:** VA-TTS-007
2. **Checked:** 2026-11-14 04:04 UTC.
3. **Level:** LEVEL 1. Fixture audio. No microphone. Not VA-INT-001.
4. **Command:** `~/.local/share/omp-voice/venv/bin/python -m pytest tests/test_barge_fixture.py::test_stop_fixture_is_whispered_before_playback_can_resume tests/test_wake_and_gain.py::test_tts_barge_frames_queue_whisper_without_stopping_playback tests/test_wake_and_gain.py::test_apply_whisper_stops_a_barge_and_does_not_open_handy -q`
5. **Result:** Passed.
6. **Hold.** Loud frames over playback arm a barge hold and queue a Whisper clip. `pause_tts_clips` is not called. `resume_tts_clips` is not called. `stop_playback` is not called. The stop fixture still stops playback only after Whisper hears `Stop.`
7. **Code.** The hold used to `SIGSTOP` the `omp-vb-` player before the words were known. Pausing speaker bleed stopped the reply and started it again. The clip now keeps playing until a confirmed stop.
8. **Live process.** Controller pid 64238 was not restarted. It still pauses on a hold. OMP pid 16590 was not reloaded.
