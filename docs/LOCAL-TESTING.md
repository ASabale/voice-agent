# Local testing

Discover the live process. Do not reuse a port from this file.

## Machine checked 2026-11-13

- macOS 26.6.2, build 25G83, arm64.
- Python 3.12.13 at `~/.local/share/omp-voice/venv/bin/python`.
- Node `v26.11.0` on `PATH`.
- `~/.local/bin/omp-voice-controller` is a symlink to this repo's `bin/omp-voice-controller` (created by `./bin/install`). Editing the repo script changes the next status or start process. The already-running controller keeps the code it loaded.
- Controller at check time: pid 64238, `IDLE`, `last_action` `sent`, `status.json` under `~/.local/state/omp-voice/`.
- At 19:40 UTC the OMP process was pid 16590. `sessions/16590.json` said port 62283 and `tty` null. `GET http://127.0.0.1:62283/status` returned `ok: true`, `version: 2`, `pid: 16590`, `speaking: false`, `agentBusy: true`, `draftLength: 0`. Read the port again. Do not POST to that bridge while `agentBusy` is true. Pid 80894 and ports 56876 and 61963 are gone.
- At 19:49 UTC VoiceBox GUI pid 20266 had `voicebox-server` pid 20305 listening on `127.0.0.1:17493`. `/health` was 200 with `model_loaded: true` and `model_size: 1.7B`. Do not exec another server. If that pid is gone, do not launch the binary. See `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md`. The 10:12 EST SIGSEGV is history, not the current process.
- `tts-playing.json` was `{"playing": false, "ended_at": ...}`. There was no `tts-playing/` directory. A new controller treats that directory as the only playback source when it exists. The process that is already running does not, until it is restarted.

## How to find the bridge

```sh
python3 -c 'import json,pathlib; p=pathlib.Path.home()/".local/state/omp-voice/sessions";
print("no sessions" if not p.exists() else "")
[print(f.name, f.read_text()) for f in sorted(p.glob("*.json"))]'
```

Then `GET http://127.0.0.1:<port>/status`. A JSON body with `ok: true` and `version: 2` is the extension in this repo. Drop a file whose pid is not alive; the controller does that in `load_session_registry`.

`omp-voice-controller status` prints the controller, the delivery decision, and `omp_bridge`. Trust `omp_bridge.url`. Ignore a failure on :17494 unless `lsof -nP -iTCP:17494 -sTCP:LISTEN` shows a listener.

## Commands that do not touch the mic

```sh
~/.local/share/omp-voice/venv/bin/python -m pytest tests/ -q
~/.local/bin/omp-voice-controller status
```

Status runs an AppleScript focus lookup and one or more GETs. It does not post a transcript.

## Commands that do touch the mic

Spoken rows A–J are in `HANDY-SCENARIO-CHECKPOINT.md`. They need the MacBook microphone and the playback procedure in that file. Do not rerun a row marked pass. Do not run G10.

## Logs

- `~/.local/state/omp-voice/controller.log`
- `~/.local/state/omp-voice/speech.log`
- `~/.local/state/omp-voice/status.json` (`mic_dropped` and `mic_invalid` once the controller process that has this code is running)
- `~/.local/state/omp-voice/tts-playing.json`

Do not copy raw transcripts into the repo. A short run record may go in `.local/voice-agent/` (gitignored).

## Do not

- Restart the OMP session.
- Kill `afplay` that you did not start.
- Change the default input or output device, or the system volume.
- POST `/transcript` or type into the focused app as a test.
- Assume VoiceBox `/health` or port 17494 is the health check.
