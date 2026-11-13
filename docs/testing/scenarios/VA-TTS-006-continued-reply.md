# VA-TTS-006 — A continued reply keeps the clip

1. **ID:** VA-TTS-006
2. **Checked:** 2026-11-14 03:58 UTC.
3. **Level:** LEVEL 4. No microphone. No VoiceBox. Not VA-INT-001.
4. **Command:** `node --experimental-strip-types --test tests/speech-queue.test.ts`
5. **Result:** Passed. 13 tests, 0 failed.
6. **Change.** A new assistant message id stops playback only when the text does not continue the reply already playing. An extension of that text, or a shorter prefix of it, leaves the clip alone. A different reply still stops. The same message id does not stop.
7. **Live process.** OMP pid 16590 was not reloaded. It still stops on every new message id. Controller pid 64238 was not restarted.
