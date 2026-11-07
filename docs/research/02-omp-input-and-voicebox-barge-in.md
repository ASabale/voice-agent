# Research 02: OMP Input Injection, VoiceBox Barge-In, and Local Audio Stack

Ticket: [issues/02-omp-input-and-voicebox-barge-in.md](../issues/02-omp-input-and-voicebox-barge-in.md)

## 1. First-Class OMP Extension API (`~/.omp/agent/extensions/`)

Inspection of `~/Development/oh-my-pi/packages/coding-agent/src/modes/controllers/extension-ui-controller.ts` (lines 100–165) and `docs/extensions.md` reveals a **major discovery**:

OMP extensions have **native, first-class methods to manipulate the live TUI input box (Draft) and submit prompts** without needing macOS `Cmd+V` keystroke simulation or window focus!

Specifically, inside any OMP extension (`~/.omp/agent/extensions/*.ts`):
- **`ctx.ui.getEditorText(): string`** — reads the current text sitting in the OMP prompt box.
- **`ctx.ui.setEditorText(text: string): void`** — sets the text in the OMP prompt box and schedules an immediate TUI repaint (`this.ctx.ui.requestRender()`).
- **`ctx.ui.pasteToEditor(text: string): void`** — pastes text directly into the OMP prompt box at the cursor (`\x1b[200~${text}\x1b[201~`) and repaints.
- **`pi.sendUserMessage(content: string, options?)`** — submits a user prompt through the exact normal prompt flow (when idle, starts a turn immediately; when streaming, steers or queues as `followUp`).

### Why this is a game-changer for Akshay's Stage 1 AND Stage 2 (Tailscale Phone):
1. **Zero focus bugs**: Even if Terminal/iTerm/Ghostty is not the frontmost macOS window while Akshay is walking around the room (or on his phone over Tailscale), an OMP extension (`omp-voice-loop.ts`) listening on a local Unix socket / HTTP port (`127.0.0.1`) or watching Handy's `history.db` can call `ctx.ui.setEditorText(current + " " + chunk)` to visibly accumulate the Draft in the OMP input box, and when `"send prompt"` is spoken, read `const draft = ctx.ui.getEditorText()`, clear the editor `ctx.ui.setEditorText("")`, and call `pi.sendUserMessage(draft)`!
2. **Stage 2 Ready**: When Akshay connects from his phone over Tailscale later, the phone sends audio/text to the exact same local endpoint and sees/submits directly into the live OMP session.

## 2. VoiceBox Playback State & Immediate Barge-In

In `~/.omp/agent/extensions/voicebox-speech.ts`:
- Currently, `play(clip)` spawns `afplay [clip.wav]` and chains promises on `genTail` and `playTail`.
- There is no cancel/barge-in hook yet.
- **Cleanest Barge-in integration**:
  - Export/expose a barge-in trigger (or combine `voicebox-speech.ts` with the voice loop extension via `pi.events` shared event bus, which OMP provides on `pi.events`!).
  - Track the active `ChildProcess` (`currentAfplay`) and a `generationEpoch` counter in `voicebox-speech.ts`.
  - When Barge-in fires (or when the user starts speaking after Wake Word):
    1. Increment `generationEpoch` so any in-flight `genTail` / `playTail` promises become no-ops and delete their temporary VoiceBox clips.
    2. `currentAfplay?.kill("SIGTERM")` to stop `afplay` audio output in <10ms.
  - Also expose `isPlaying` state so the Voice Controller knows when `afplay` is outputting audio to the room speakers.

## 3. Local Wake-Word & Mic Silence Detection on this Mac

Checked installed runtimes:
- `/Applications/Handy.app/Contents/MacOS/handy` is already running and has CoreAudio mic access (`MacBook Pro Microphone (CoreAudio)`).
- System `swift` (`/usr/bin/swift`) has native access to `AVFoundation` / `AVAudioEngine` / `Speech` (`SFSpeechRecognizer` / `SpeechAnalyzer` on macOS 26), and `~/Development/venv` has Python 3 + `numpy`.
- We can install `openwakeword` + `sounddevice` (or `pyaudio`) into `~/Development/venv` (or a dedicated lightweight venv) for `<1% CPU` always-on `"Hey Jarvis"` detection + 5-second RMS/Silero VAD silence detection.
