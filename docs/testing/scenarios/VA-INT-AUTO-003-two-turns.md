# VA-INT-AUTO-003 — Two turns, playback kept alive

1. **ID:** VA-INT-AUTO-003
2. **Level:** LEVEL 3. Real OMP, real VoiceBox, real `afplay`. Not a microphone test.
3. **Do not:** POST to pid 16590. Do not start a second VoiceBox. Do not use `omp -p` for a playback check. Print mode exits and `session_shutdown` aborts the generate.
4. **What worked:** An interactive `omp` on a pty, with the voice extension, stays up after the first answer. `omp-voice-controller start` from that process finds pid 64238 already running and returns.
5. **Turn 1:** Prompt `Respond with exactly: Voice integration test successful.` Pid 25448, bridge 63520. Assistant text was that sentence. `speech.log` `omp-vb-25448-1.wav`, 24 kHz, 59520 frames. Status then said `agentBusy` false.
6. **Turn 2:** `POST http://127.0.0.1:63520/transcript` with `Reply with exactly: Second voice check complete. Send that.` Result `action: sent`, draft `reply with exactly second voice check complete`. The parser lowercased it. Assistant text was `second voice check complete` (27 characters). `omp-vb-25448-2.wav`, 24 kHz, 46080 frames. Slot `tts-playing/25448.json`: `afplay_pid` 25917, `playback_rate` 1.18, `started_at` 1794600373.748, `ended_at` 1794600376.374, `reason` `end`. Expected play time is 1.92 / 1.18 = 1.63 s. The slot lasted 2.63 s, so the player was not cut at the start. `reason: end` is also what a stop writes, so this is not an exit code.
7. **Earlier same sentence:** Pid 25014, `omp-vb-25014-1.wav`, 74880 frames. Slot `tts-playing/25014.json`: `afplay_pid` 25103, 1794600285.43 to 1794600289.075 (3.65 s). Expected at 1.18× is 2.64 s.
8. **User session:** `sessions/16590.json` was byte-for-byte the same after both processes. `GET /status` stayed `agentBusy` true. No POST to port 62283.
9. **Not done:** No wake, no Handy transcript, no interrupt, no proof a person heard the speaker.
10. **Next:** Interrupt playback of an isolated session. Do not route that through the live controller if it can submit to pid 16590.
