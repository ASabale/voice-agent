# voice-agent

Hands-free voice for a local [OMP](https://github.com/can1357/omp) (`oh-my-pi`) session on a Mac.

You say **Hey Jarvis**, dictate across pauses, and say **send prompt**. The words land in the OMP draft and are submitted from there. OMP’s reply is spoken back on this Mac in your cloned voice. Saying **Hey Jarvis** again stops playback so you can talk over it.

## Why this exists

Working with an OMP agent on a MacBook usually means typing into the terminal, watching the output on screen, and typing the next response. Dictation tools like Wispr Flow speed up the typing part, and [Handy](https://github.com/cjpais/Handy) makes speech-to-text completely local by typing spoken thoughts into the focused text box. Pairing that with [VoiceBox](https://github.com/jamiepine/voicebox) — which clones your voice locally across multiple languages and model quality tiers — completes the loop so the OMP agent can both hear you and speak back.

`voice-agent` connects those pieces so you can work with your OMP session completely hands-free without looking at the screen:

1. **Hands-free command grammar (`grammar.json`)**: Wake Handy by voice (**Hey Jarvis**), dictate in chunks where each ~5-second pause appends to the OMP draft without submitting, recover from mistakes or misinterpretations (**scratch that**, **clear draft**, **cancel that**), and submit when ready (**send prompt**).
2. **Memory-aware model tiering (`1.7B ↔ 0.6B`)**: When an online model is unavailable or you run a large local model as the OMP agent's brain, unified memory gets tight. When `~/.local/state/strata/omp-autostart.json` reports `"engine": "flash"`, the controller automatically switches both Handy and VoiceBox down to their **0.6B** models so the entire stack (LLM + STT + TTS) fits in memory and runs 100% locally. When the large local model unloads, it restores both to **1.7B** quality.
3. **Screen-free conversational collaboration (`skills/conversational-collaboration/`)**: Terminal output full of tables, diffs, and file paths does not work when read aloud. The bundled `conversational-collaboration` skill shapes how the agent speaks while you are away from the screen — staying silent during routine work and speaking short, high-signal beats only when a finding, milestone, or decision needs your input.

## Architecture

This is a local listener and an OMP extension. It does not ship its own speech engine or a separate middleman LLM. Three apps you install yourself do the work:

| App | What it does here |
|---|---|
| [OMP](https://github.com/can1357/omp) (oh-my-pi) | The terminal session you are talking to. The extension in this repo types into its draft, submits, and speaks the reply. |
| [Handy](https://github.com/cjpais/Handy) | Local speech to text. The listener starts and stops recording. You do not have to keep Handy’s window open. |
| [VoiceBox](https://github.com/jamiepine/voicebox) | Local text to speech. One cloned voice profile on this Mac speaks the reply across configurable quality tiers (`1.7B` / `0.6B`). The profile name is local; this repo does not store it. |

```mermaid
flowchart LR
  mic[Mic] --> ctrl[omp-voice-controller]
  ctrl --> handy[Handy]
  handy --> bridge["OMP extension ephemeral port"]
  bridge --> omp[OMP session]
  omp --> bridge
  bridge --> vb["VoiceBox :17493"]
  vb --> play[Speaker]
  play -->|stops when you say Hey Jarvis| ctrl
```

## What you need

- macOS on Apple Silicon or Intel
- Homebrew
- A microphone, and permission for Handy and the terminal to use it
- The three apps above

Python packages for the wake word and silence detection are installed into `~/.local/share/omp-voice/venv` by the install script. You do not need a separate Python project.

## Set up

### 1. OMP

```sh
brew tap can1357/tap
brew install omp
```

Open the OMP session you want to talk to. The voice extension binds an ephemeral `127.0.0.1` port and writes `~/.local/state/omp-voice/sessions/<pid>.json`. The controller reads that file. Port `17494` is only for a legacy build that is actually listening there. A focused text control in another app is a paste, not a bridge send.

### 2. Handy

Install [Handy](https://github.com/cjpais/Handy) so `Handy.app` is in `/Applications`. On first launch, allow the microphone and download an English model. Leave the app installed. In Handy’s settings, turn off “mute while recording” if that option is on.

### 3. VoiceBox

Install [VoiceBox](https://github.com/jamiepine/voicebox) and leave it running at `http://127.0.0.1:17493`. Create one voice profile in the app and remember its **name**.

Download a Qwen text-to-speech model in VoiceBox (0.6B or 1.7B). The listener uses **1.7B** by default. If a local model state file at `~/.local/state/strata/omp-autostart.json` says `"engine": "flash"`, it switches Handy and VoiceBox to the **0.6B** models so they can sit beside a large local model in memory, and switches both back to **1.7B** when that file no longer says `flash`. Without that file, both stay on 1.7B. Download both sizes only if you use that switch.

### 4. This repository

```sh
git clone https://github.com/ASabale/voice-agent.git
cd voice-agent
./bin/install "Your VoiceBox Profile Name"
```

`./bin/install` writes that name to `~/.local/state/omp-voice/profile`, creates the Python environment, and symlinks this checkout into the paths OMP and the listener actually run:

- `bin/omp-voice-controller` → `~/.local/bin/omp-voice-controller`
- `bin/omp-handy-hook` → `~/.local/bin/omp-handy-hook`
- `extension/voicebox-speech.ts` → `~/.omp/agent/extensions/voicebox-speech.ts`
- `grammar.json` → `~/.local/share/omp-voice/grammar.json`
- `skills/conversational-collaboration` → `~/.omp/agent/managed-skills/conversational-collaboration`

`OMP_VOICEBOX_PROFILE` overrides the profile file when it is set. Edit this checkout. Do not keep a second copy under `~/.local` or `~/.omp`.

Restart the OMP session so it picks up the extension (`/restart` inside OMP). There is no reload command. Then:

```sh
omp-voice-controller start
```

Say **Hey Jarvis**, speak, pause, and say **send prompt**.

## Talking to it

| You say | What happens |
|---|---|
| Hey Jarvis | Playback stops, if any, and dictation starts |
| a pause of about 5 seconds | The chunk is transcribed into the OMP draft and dictation continues |
| send prompt / send now / submit / all done / over | The draft is submitted. Words before `over` are kept |
| stop / pause listening / go to sleep | Dictation stops and the draft is kept |
| scratch that / undo | The last chunk is removed |
| clear draft / clear everything | The draft is emptied |
| cancel that / discard | The current unpasted chunk is discarded and the listener returns to idle |

Command phrases are matched from `grammar.json`: one word from each slot, in order. Closing Handy’s window returns the listener to idle and does not open it again.

```sh
omp-voice-controller status
omp-voice-controller stop
```

Logs and status stay on the machine, under `~/.local/state/omp-voice/`. Handy’s transcription history and VoiceBox audio are also local. None of that is in this repository.

## What is in the repo

| Path | Role |
|---|---|
| `bin/omp-voice-controller` | Wake word, silence chunking, Handy, memory-aware model tiering (`1.7B ↔ 0.6B`), microphone |
| `bin/omp-handy-hook` | Forwards one Handy transcript into the controller |
| `extension/voicebox-speech.ts` | OMP extension: draft history, submit, barge-in, VoiceBox speech |
| `grammar.json` | Ordered command slots for wake, submit, undo, clear, pause, and cancel |
| `skills/conversational-collaboration/` | Skill that keeps spoken replies concise and actionable when you are not looking at the screen |
| `docs/setup.md` | The same first-time steps, in longer form |

## Roadmap (Next Stages)

1. **Remote session control (away from the laptop)**: Bridge voice and session control over a private network (such as Tailscale) so you can talk to your MacBook's OMP agent and get work done while away from your desk or laptop.
2. **Command authorization & sandboxing**: Rather than inventing a second sandbox layer, wire voice command authorizations directly into OMP's built-in sandboxing and approval gates so remote/hands-free execution stays safe and reliable.
3. **Cross-session memory**: Persist structured context across OMP sessions automatically.

## License

MIT. See [LICENSE](LICENSE).
