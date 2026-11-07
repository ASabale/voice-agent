# Build and smoke-test the hands-free OMP voice controller

Type: task
Status: open
Blocked by: 01, 02, 03, 04

## Question

Implement the hands-free voice controller daemon + Handy transcription hook, wire start/stop commands (e.g. `/voice-loop` in `omp` or a CLI launcher), and verify end-to-end:
1. Say `"Hey Jarvis"` → Wake cue plays, Handy starts recording.
2. Speak Chunk 1 → pause 5 seconds → Chunk 1 pastes into `omp` input box without pressing `Enter` + tick cue plays + next chunk recording begins.
3. Speak Chunk 2 ending with `"send prompt"` (or say `"send prompt"` standalone) → `"send prompt"` is stripped, Chunk 2 appends, `Enter` is pressed, `omp` responds, VoiceBox speaks, and `"Hey Jarvis"` barges in cleanly.
