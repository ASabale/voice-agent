# VA-TTS-011 — A period does not split a growing sentence

1. **ID:** VA-TTS-011
2. **Checked:** 2026-11-13 23:29 UTC.
3. **Level:** LEVEL 4. No microphone. No VoiceBox. Not VA-INT-001.
4. **Command:** `node --experimental-strip-types --test tests/speech-queue.test.ts`
5. **Result:** Passed. 14 tests, 0 failed.
6. **Heard.** At 23:27:51 a 138-character clip was requested. At 23:27:53 it was aborted and the queue was dropped with reason `epoch`. The running session still does that.
7. **Change.** A new message id stops playback only when the words are not the same reply. `I will leave.` and `I will leave the player.` stay one reply. `A different answer.` still stops playback.
8. **Live process.** OMP pid 16590 was not reloaded. Controller pid 64238 was not restarted.
