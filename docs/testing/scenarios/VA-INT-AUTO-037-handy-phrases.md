# VA-INT-AUTO-037 — Handy phrases through the controller

1. **ID:** VA-INT-AUTO-037
2. **Checked:** 2026-11-13 20:53 UTC.
3. **Level:** LEVEL 3 for the transcription. The controller check is the decision only. Not the microphone. Not LEVEL 4.
4. **Handy:** `handy --transcribe-file` on the selected Qwen3-ASR 0.6B model. No toggle and no playback. `tests/fixtures/hey-jarvis-say.wav` came back as `Hey Jarvis.` in 60 ms. `hold-on-say.wav` came back as `Hold on a second.` in 66 ms. `sentence-stop-say.wav` came back as `The sentence ends with stop.` in 71 ms. Records are `.local/voice-agent/runs/VA-INT-AUTO-037-*.json`.
5. **Controller:** `tests/test_handy_file_phrases.py` uses those strings plus the VA-INT-AUTO-036 results `Good morning.` and `Stop.`. `stop_playback` and `resume_tts_clips` are stubs. `enter_dictating` is replaced on the instance. `dispatch_transcript` fails the test if called.
6. **Wake:** `Hey Jarvis.` is a wake. The idle-verify path records one dictation reason and does not call the real method.
7. **Idle:** `Good morning.` is not a wake and not a command. `Stop.` matches the grammar action `paused`, but idle verify does not dispatch it and does not stop playback.
8. **Over TTS:** `Stop.` and `Hold on a second.` each call the stubbed stop. The sentence `The sentence ends with stop.` does not. That hold resumes instead.
9. **Live files:** `status.json` stayed `IDLE` at `updated_at` 1794598062.972905. `controller.log` mtime stayed 1794598062.9733093.
10. **Still blocked:** LEVEL 4 still needs a second input. These strings never passed through the live controller.
