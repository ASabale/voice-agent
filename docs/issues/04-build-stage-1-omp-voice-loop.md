# Build Stage 1 OMP Voice Loop (Extension + Voice Controller)

Type: task
Status: resolved
Blocked by: 03

## Question

Implement and verify the Stage 1 OMP Voice Loop specified in [spec.md](../spec.md):
1. Update `~/.omp/agent/extensions/voicebox-speech.ts` (or companion extension `~/.omp/agent/extensions/omp-voice-loop.ts`) to:
   - Support immediate Barge-in (`afplay` termination + queue flush).
   - Expose local control HTTP server on `127.0.0.1:17494` (`/status`, `/barge-in`, `/transcript`).
   - Append dictated chunks to the OMP editor Draft via `ctx.ui.getEditorText()` / `ctx.ui.setEditorText()` without submitting, and strip/execute command phrases (`"send prompt"` -> `pi.sendUserMessage(draft)`, `"pause listening"`, `"cancel that"`).
2. Create the local Voice Controller (`~/.local/bin/omp-voice-controller`) that:
   - Detects `"Hey Jarvis"` in `Idle`, triggers Barge-in, plays the Wake chime, and starts `handy --toggle-transcription`.
   - Detects 5-second silence pauses in `Dictating`, stops `handy --toggle-transcription` to flush the chunk to `history.db`, forwards the transcript to `127.0.0.1:17494/transcript`, plays the Chunk tick, and automatically restarts `handy --toggle-transcription` for the next chunk until `"send prompt"` or `"pause listening"` (or 15s total silence timeout).
3. Smoke-test end-to-end (chunk append, `"send prompt"` submit, and Barge-in).

## Answer

Implemented and verified:
- Updated `~/.omp/agent/extensions/voicebox-speech.ts` with the local HTTP bridge (`127.0.0.1:17494`), `parseVoiceTranscript()` (appends 5s pause chunks via `ctx.ui.setEditorText()`, strips `"send prompt"` and submits via `pi.sendUserMessage()`), `/voice` slash command, `bargeIn()` (`afplay` kill + queue flush), and auto-start of `omp-voice-controller` on `session_start`.
- Created `~/.local/bin/omp-voice-controller` and `~/.local/bin/omp-handy-hook` backed by `~/.local/share/omp-voice/venv` (`openwakeword` `hey_jarvis` ONNX + Silero VAD + `sounddevice`).
- Verified multi-chunk accumulation, `"send prompt"` stripping/submission, Barge-in, and background daemon startup (`pid 28902` in `IDLE`).
