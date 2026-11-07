# Lock the Stage 1 Voice Controller architecture and build ticket

Type: grilling
Status: resolved
Blocked by: 01, 02

## Question

Given the findings from [How should the Voice Controller drive Handy for 5-second pause chunking and Send Phrase interception?](01-handy-chunking-and-hook-seam.md) and [How should the Voice Controller inject Draft text and Enter into the OMP Session and coordinate Barge-in with VoiceBox?](02-omp-input-and-voicebox-barge-in.md), confirm the final Stage 1 implementation slice before dispatching `builder`.

## Answer

Locked **Option A (OMP Extension + Local Voice Controller Daemon)**:
- Route Handy transcripts directly into the OMP session via an OMP extension (`ctx.ui.getEditorText` / `ctx.ui.setEditorText` + `pi.sendUserMessage`), rather than relying on macOS `Cmd+V` window focus.
- A local Voice Controller monitors the mic for the Wake Word (`"Hey Jarvis"`) and 5-second silence pauses during `Dictating`, driving `handy --toggle-transcription` and playing non-verbal Audio Cues (Wake chime, Chunk tick, Send chime, Cancel tone).
- Spoken command phrases (`"send prompt"`, `"pause listening"`, `"cancel that"`) are stripped/handled before touching the OMP Draft: `"send prompt"` appends any leading text and submits the full Draft (`pi.sendUserMessage`); `"pause listening"` appends any leading text and returns to `Idle`; `"cancel that"` discards the chunk and returns to `Idle`.
- Speaking `"Hey Jarvis"` while VoiceBox (`afplay`) is playing triggers Barge-in: kills `afplay` and clears the pending `voicebox-speech.ts` playback queue before starting capture.
- Spec written to [spec.md](../spec.md); implementation tracked in [Build Stage 1 OMP Voice Loop (Extension + Voice Controller)](04-build-stage-1-omp-voice-loop.md).
