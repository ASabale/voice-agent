# VA-INT-AUTO-041 — Stop fixture cuts real playback

1. **ID:** VA-INT-AUTO-041
2. **Checked:** 2026-11-13 21:28 UTC.
3. **Level:** Fixture-fed interruption of real VoiceBox playback. Not the microphone. Not acoustic echo cancellation. Not VA-INT-001.
4. **Failure that was measured first.** `stop-say.wav` is 0.63 s, 7 frames. Frames 4–6 are hot (`vad` 0.86, 0.99, 0.78 and rms 4130, 6303, 2605). Frame 3 is loud but `vad` 0.49, under 0.55. The bleed floor was updated with frames 4 and 5 before the hold, so frame 6 needed rms above about 15000 and the run reset. When a hold did start on the last loud frame, the onset audio was discarded, two quiet frames called `resume_tts_clips`, and Whisper was never asked. Thresholds 0.55 and 320 were not the miss.
5. **Change.** A hot frame is not added to the bleed floor. The eight-frame pre-roll is kept when the hold starts, and `pause_tts_clips` still runs at that moment. Two quiet frames with that clip go to Whisper before any resume. `Stop.` calls `stop_playback`. Anything else resumes once. An empty hold still resumes. Silence does not pause.
6. **Playback.** Isolated omp pid 50805, bridge 50354. The prompt was submitted, action `sent`. `afplay` pid 50930 was alive. The fixture log said `Audio source fixture (16 frames, microphone not opened)`.
7. **Stages.** `speaking` true. Hold `rms=2605 vad=0.78 floor=69 hot=3 frames=7`. Clip `frames=7 peak=25244 voice=false`. Whisper text `stop.`. `stop_playback` 0.589 s after the hold. The afplay pid was gone and still gone 0.8 s later. State stayed `IDLE`.
8. **Next turn.** `Reply with exactly: Second voice check complete. Send prompt.` Action `sent`. A new playback started. The old afplay pid did not return.
9. **Left alone.** Pid 16590 and pid 64238. `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. No second VoiceBox server. `pause_tts_clips`, `resume_tts_clips`, `stop_playback`, and `kill_tts_clips` were the real functions, limited to pid 50805.
10. **Checks.** `pytest tests/test_barge_fixture.py tests/test_wake_and_gain.py::test_two_quiet_frames_release_a_barge_hold_while_playback_continues -q`. Runner: `python scripts/run_interrupt_probe.py`.
