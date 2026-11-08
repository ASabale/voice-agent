# First-time setup

One checkout is the program. `./bin/install` creates a Python environment and symlinks that checkout into the two places macOS actually runs. Edit the checkout. Do not keep a second copy under `~/.local` or `~/.omp`.

## 1. OMP

OMP is the terminal session that receives what you say and writes the reply.

```sh
brew tap can1357/tap
brew install omp
```

Start a session in the terminal you want to talk to. The voice extension binds `127.0.0.1:17494` when that session starts. The newest session takes the port.

## 2. Handy

Handy is the speech-to-text app. Install [Handy](https://github.com/cjpais/Handy) and put `Handy.app` in `/Applications`.

On first launch, grant the microphone permission and download the English model it offers. Leave the app installed. The listener starts and stops it. You do not have to open it yourself.

In Handy settings, turn off "mute while recording" if that option is on. The listener also sets this when it starts.

## 3. VoiceBox

VoiceBox speaks the reply on this Mac. Install [VoiceBox](https://github.com/jamiepine/voicebox) and leave it running at `http://127.0.0.1:17493`.

Create one voice profile in the VoiceBox app. Remember the profile **name**. The profile id stays on this Mac and is not written to the repository.

## 4. This repository

```sh
git clone https://github.com/ASabale/voice-agent.git
cd voice-agent
./bin/install "Your Profile Name"
```

That writes the name to `~/.local/state/omp-voice/profile`, installs Python packages into `~/.local/share/omp-voice/venv`, and links:

- `bin/omp-voice-controller` → `~/.local/bin/omp-voice-controller`
- `bin/omp-handy-hook` → `~/.local/bin/omp-handy-hook`
- `extension/voicebox-speech.ts` → `~/.omp/agent/extensions/voicebox-speech.ts`
- `grammar.json` → `~/.local/share/omp-voice/grammar.json`
- `skills/conversational-collaboration` → `~/.omp/agent/managed-skills/conversational-collaboration`

`OMP_VOICEBOX_PROFILE` overrides the profile file when it is set.

Reload the OMP session so it loads the extension. Then:

```sh
omp-voice-controller start
```

Say **Hey Jarvis**, speak, and say **send prompt**. Playback stops when you say **Hey Jarvis** again. Closing Handy's window returns the listener to idle and does not open it again.

Logs and status stay on the machine: `~/.local/state/omp-voice/`.
