# VA-TTS-009 — A growing sentence does not repeat its opening

1. **ID:** VA-TTS-009
2. **Checked:** 2026-11-14 04:16 UTC.
3. **Level:** LEVEL 4. No microphone. No VoiceBox. Not VA-INT-001.
4. **Command:** `node --experimental-strip-types --test tests/speech-queue.test.ts`
5. **Result:** Passed. 14 tests, 0 failed.
6. **Heard.** At 23:22:39 a 129-character clip was requested. At 23:22:42 it was aborted and the queue was dropped. At 23:22:50 a 127-character clip was requested and then played. The opening words were in both. The running session still does that.
7. **Change.** A longer sentence that starts with words already queued speaks only the new tail. `I will leave.` followed by `I will leave the player.` leaves `the player`. The first short sentence waits for the next sentence or the end of the message instead of playing immediately.
8. **Live process.** OMP pid 16590 was not reloaded. It still speaks that opening twice. Controller pid 64238 was not restarted.
