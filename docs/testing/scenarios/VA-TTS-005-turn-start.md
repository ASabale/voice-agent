# VA-TTS-005 — A turn start does not abort the clip

1. **ID:** VA-TTS-005
2. **Checked:** 2026-11-14 03:52 UTC.
3. **Level:** LEVEL 4. No microphone. No VoiceBox. Not VA-INT-001.
4. **Command:** `node --experimental-strip-types --test tests/speech-queue.test.ts`
5. **Result:** Passed. 12 tests, 0 failed.
6. **Cause.** The controller ignored `Leave the leave the leave the leave.` and did not stop playback. `speech.log` then aborted a clip and dropped the queue with reason `epoch`. That bump is `stopPlayback`. `turn_start` called it for a tool round and for a streamed reply. The in-flight sentences were forgotten and spoken again. The mic heard that replay.
7. **Change.** `onTurnStart` does not stop playback. `stopPlayback` still bumps the epoch. A user interrupt still calls `bargeIn`.
8. **Live process.** OMP pid 16590 was not reloaded. It still aborts on `turn_start`. Controller pid 64238 was not restarted.
