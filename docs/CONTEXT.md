# OMP Voice Loop

A phased, eyes-free voice interface for operating Oh My Pi (OMP) away from the keyboard — first in the room via Handy + VoiceBox, then from a phone over Tailscale, and later through a conversational Broker with cross-session memory and directory sandboxing.

## Language

**OMP Session**:
The interactive root Oh My Pi terminal session that acts as the primary conversational and planning brain in Stage 1. It already has hybrid cloud + local models, extensions (`voicebox-speech.ts`), tools, and memory (`memory://root`).
_Avoid_: Building a separate middleman LLM in Stage 1 that duplicates OMP's own intent understanding and session state.

**Voice Controller**:
The lightweight local daemon/sidecar that bridges microphone audio, Wake Word detection, Handy transcription, and keystroke/PTY injection into the OMP Session without using an LLM of its own.
_Avoid_: Calling the Voice Controller an "agent" or "broker".

**Wake Word**:
The spoken phrase (default `"Hey Jarvis"`) that moves the Voice Controller from Idle to Dictating, or triggers Barge-in while VoiceBox is playing.

**Idle**:
The Voice Controller is listening only for the Wake Word; room conversation is ignored and never pasted into OMP.

**Dictating**:
The active multi-chunk capture state entered after the Wake Word. Each spoken section followed by a **Pause** (5 seconds of silence) is transcribed by Handy and appended to the **Draft** in the OMP input box without pressing Enter. The controller stays in Dictating until the human says the **Send Phrase**, **Pause Phrase**, or **Cancel Phrase**.

**Pause**:
A 5-second silence during Dictating that flushes the current spoken audio chunk through Handy into the OMP input box as part of the Draft, emits a subtle audio tick, and keeps listening for the next chunk.

**Draft**:
The unsubmitted text accumulated in the OMP prompt input box across one or more dictated chunks before Enter is pressed.

**Send Phrase**:
The spoken command (default `"send prompt"`) that strips the command phrase from the transcript (if spoken at the end of a chunk), pastes any remaining text, sends `Enter` to submit the Draft to the OMP Session, plays a sent chime, and returns the Voice Controller to Idle.

**Pause Phrase**:
The spoken command (default `"pause listening"`) that flushes any pending speech to the Draft without pressing Enter and returns the Voice Controller to Idle.

**Cancel Phrase**:
The spoken command (default `"cancel that"`) that discards the current unpasted audio chunk and returns the Voice Controller to Idle.

**Barge-in**:
Speaking the Wake Word while VoiceBox (`afplay`) is speaking an OMP response. Immediately kills `afplay` playback and enters Dictating.

**Audio Cues**:
Short non-verbal sounds confirming state transitions when not looking at the laptop screen: Wake chime (listening started), Chunk tick (5s pause pasted to Draft), Send chime (Enter pressed), and Cancel tone.

**Broker (Future Stage)**:
A future real-time duplex voice model that converses naturally with the human, asks confirmations, and writes structured prompts to underlying worker sessions. Deferred until Stage 1 (direct OMP Session voice loop) and Stage 2 (Tailscale phone audio bridge) are proven.
