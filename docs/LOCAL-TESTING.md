# Local testing

Discover the live process. Do not reuse a port from this file.

## Machine checked 2026-11-13

- macOS 26.6.2, build 25G83, arm64.
- Python 3.12.13 at `~/.local/share/omp-voice/venv/bin/python`.
- Node `v26.11.0` on `PATH`.
- `~/.local/bin/omp-voice-controller` is a symlink to this repo's `bin/omp-voice-controller` (created by `./bin/install`). Editing the repo script changes the next status or start process. The already-running controller keeps the code it loaded.
- Controller at check time: pid 64238, `IDLE`, `last_action` `sent`, `status.json` under `~/.local/state/omp-voice/`.
- OMP pid 80894 was alive. Its registry file is `~/.local/state/omp-voice/sessions/80894.json` with `pid`, `port`, `tty`, `startedAt`. The port changed during the same hour (56876, then 57042) without this run restarting OMP. Read the file again.
- VoiceBox.app pid 29277 was running. Nothing was listening on `127.0.0.1:17493`, and `curl http://127.0.0.1:17493/health` failed. The extension still calls `http://127.0.0.1:17493`. Do not restart VoiceBox from a test.
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
