# VA-TTS-012 — A later sentence does not repeat its spoken opening

1. **ID:** VA-TTS-012
2. **Checked:** 2026-11-13 23:32 UTC.
3. **Level:** LEVEL 4. No microphone. No VoiceBox. Not VA-INT-001.
4. **Command:** `node --experimental-strip-types --test tests/speech-queue.test.ts`
5. **Result:** Passed. 14 tests, 0 failed.
6. **Heard.** At 23:31:01 a 151-character clip was aborted and the queued sentences were dropped with reason `epoch`. The running session still does that.
7. **Change.** `speechAfterSpoken` strips an opening that matches the last queued chunk, not only an opening that matches every chunk joined together. `The reply was cut.` followed by `I will leave.` then `I will leave the player.` leaves `the player`.
8. **Live process.** OMP pid 16590 was not reloaded. Controller pid 64238 was not restarted.
