# How should the Voice Controller inject Draft text and Enter into the OMP Session and coordinate Barge-in with VoiceBox?

Type: research
Status: resolved
Blocked by:

## Question

Inspect OMP's extension API (`~/.omp/agent/extensions/voicebox-speech.ts` and `/opt/homebrew/Cellar/omp/18.18.0/`) and macOS terminal injection options to answer:
1. Can an OMP extension (loaded alongside `voicebox-speech.ts`) programmatically append text to the OMP prompt input box and/or submit a user message, or should text + `Enter` be injected via macOS keystrokes (`enigo` / `osascript` / `CGEvent`) or `tmux send-keys` into the focused OMP terminal?
2. How does `voicebox-speech.ts` currently play audio (`afplay` child processes), and what is the cleanest way for the Voice Controller to (a) know when VoiceBox is actively speaking (to avoid acoustic self-triggering) and (b) immediately kill `afplay` and drain the `voicebox-speech.ts` playback queue on Barge-in when the Wake Word is spoken?
3. What local Wake Word + VAD library is already installed in Python/Node on this Mac (e.g., `openwakeword`, `pvporcupine`, `silero-vad`, `webrtcvad`, `pyaudio`, `sounddevice`, `mlx`) so we don't install unnecessary heavy dependencies?

## Answer

OMP extensions have **native editor & submit APIs**: `ctx.ui.getEditorText()`, `ctx.ui.setEditorText(text)`, `ctx.ui.pasteToEditor(text)`, and `pi.sendUserMessage(text)` (`extension-ui-controller.ts:100-165`). An OMP extension can therefore append 5s dictated chunks directly into the visible OMP input box and submit on `"send prompt"` with zero macOS window-focus dependence—and this same local bridge works for Stage 2 (Tailscale phone). `voicebox-speech.ts` can expose `afplay` kill + queue drain on Barge-in via `pi.events` or a local control socket. Detail: [research/02-omp-input-and-voicebox-barge-in.md](../research/02-omp-input-and-voicebox-barge-in.md).
