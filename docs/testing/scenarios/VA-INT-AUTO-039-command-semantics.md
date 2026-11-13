# VA-INT-AUTO-039 — Stop, pause, resume, hold on

1. **ID:** VA-INT-AUTO-039
2. **Checked:** 2026-11-13 20:58 UTC.
3. **Level:** Decision only. Not an audio-path result. Not VA-INT-001.
4. **Stop:** A playback clip whose tokens are only `stop` cuts speech and stays `IDLE`. It does not open Handy. The same word in the grammar is action `paused`: during dictation it keeps the draft and leaves dictation. An idle verify of `Stop.` does not dispatch and does not stop playback, because nothing is playing on that path.
5. **Pause:** Grammar action `paused`, same as stop for dictation. It is not a playback barge. `forSpeech` rewrites spoken `stop` to `the pause command` and leaves the word `pause` unchanged. `the pause command` is not a barge, so the rewritten speech does not cut itself.
6. **Resume:** Not a wake and not a grammar action. The only resume in the controller is `resume_tts_clips` after a hold that was not a stop. There is no spoken resume.
7. **Hold on a second:** A playback barge, same cut as stop, and not a pause phrase. `forSpeech` leaves it unchanged. Over TTS the stubbed stop runs. `pause`, `the pause command`, and `resume` do not stop; each of those holds resumes.
8. **Checks:** `pytest tests/test_command_semantics.py -q` passed. `node --experimental-strip-types --test tests/match_command.test.ts` passed, 32 tests. `stop_playback` and `resume_tts_clips` were stubbed in the Python test. That stub is not evidence of a real stop.
9. **Not this test:** No microphone, no Handy toggle, no VoiceBox generate, no second turn.
