# Hands-free Voice Loop for OMP (Handy + VoiceBox)

Label: `wayfinder:map`

## Destination

A working **Stage 1 In-Room Hands-Free Voice Loop** for the focused OMP terminal session on this Mac: say the **Wake Word** (`"Hey Jarvis"`), speak in chunks where each **5-second Pause** transcribes via Handy and appends to the OMP input box without pressing Enter, and say the **Send Phrase** (`"send prompt"`) to press Enter — with **Audio Cues** for eyes-free feedback and **Barge-in** to interrupt VoiceBox (`afplay`) playback.

## Notes

- Domain: OMP hands-free voice loop. Glossary: [CONTEXT.md](CONTEXT.md).
- Tracker: local markdown under `.scratch/omp-voice-loop/`.
- Execution override: carry execution into the map once the technical research tickets settle the exact Handy + OMP integration seam.
- Architectural decision locked with Akshay: **Talk directly to the focused OMP Session first** (no separate LLM middleman/broker in Stage 1). OMP's root session already understands intent, holds conversation state, and speaks replies via `~/.omp/agent/extensions/voicebox-speech.ts`. Adding a separate broker LLM before Stage 1 works adds routing/invocation complexity for zero gain.
- Skills every session should consult: `grilling`, `domain-modeling`, `research`, `prototype`.

## Decisions so far

- **Direct OMP Session vs. separate conversational Broker for Stage 1** — Use the focused OMP terminal session directly as the brain in Stage 1; defer a separate real-time duplex conversational Broker until after the hands-free loop and Tailscale phone bridge work.
- **Dictation state machine** — Wake-once continuous session (`Idle → Dictating → Idle`): `"Hey Jarvis"` starts listening (with chime); each 5s silence pause transcribes and pastes to the OMP Draft without Enter (with tick); `"send prompt"` presses Enter and returns to Idle; `"pause listening"` returns to Idle keeping Draft; `"cancel that"` aborts chunk.
- [How should the Voice Controller drive Handy for 5-second pause chunking and Send Phrase interception?](issues/01-handy-chunking-and-hook-seam.md) — Drive the warm running Handy app via `handy --toggle-transcription` (66ms start, 170ms Metal decode) triggered by a 5s silence timer; intercept transcripts before paste to strip command phrases.
- [How should the Voice Controller inject Draft text and Enter into the OMP Session and coordinate Barge-in with VoiceBox?](issues/02-omp-input-and-voicebox-barge-in.md) — Use OMP's native extension API (`ctx.ui.setEditorText` / `ctx.ui.getEditorText` + `pi.sendUserMessage`) and cancel `afplay` + `voicebox-speech.ts` queue on Barge-in.
- [Lock the Stage 1 Voice Controller architecture and build ticket](issues/03-lock-stage-1-voice-controller-spec.md) — Option A locked: OMP extension bridge (`127.0.0.1:17494`) + `~/.local/bin/omp-voice-controller` daemon (`"Hey Jarvis"` wake, 5s pause chunking, `"send prompt"` submit, Barge-in). Spec in [spec.md](spec.md).
- [Build Stage 1 OMP Voice Loop (Extension + Voice Controller)](issues/04-build-stage-1-omp-voice-loop.md) — Shipped and running (`~/.omp/agent/extensions/voicebox-speech.ts` + `~/.local/bin/omp-voice-controller` + `~/.local/bin/omp-handy-hook`).

## Not yet specified

- **Stage 2 — Tailscale Phone Voice Bridge**: Speak on iPhone/phone over Tailscale → transcribe on Mac → inject into OMP → stream/play VoiceBox audio reply back on the phone.
- **Stage 3 — Cross-Session Memory Bank**: Structured cross-session memory layer (`memory://` / knowledge bank) that persists context across OMP sessions automatically.
- **Stage 4 — Directory Sandboxing & OS Safety**: Encapsulating where the AFK agent can operate safely (restricting filesystem/shell/browser blast radius to an approved directory/policy when driven remotely).
- **Stage 5 — Real-Time Duplex Conversational Broker**: Full-duplex voice model that converses, confirms intent verbally, and dispatches refined prompts to underlying OMP sessions.

## Out of scope

- Building the real-time duplex Broker LLM before Stage 1 (in-room OMP terminal voice loop) is working.
- Replacing Handy's ASR engine (`Qwen3-ASR-1.7B-Q8_0.gguf`) or VoiceBox's TTS engine (`qwen-tts-0.6B`).
