# OMP session readiness

Checked 2026-11-13 19:46 UTC. Re-read the registry before using any port in this file.

`agentBusy` and the editor draft are different. An empty draft does not mean the session is idle. `tty: null` does not mean the bridge is broken. VoiceBox health is not this check.

## What `/status` means

The extension in `extension/voicebox-speech.ts` answers `GET /status` with version 2. `agentBusy` is `!ctx.isIdle()`. If `isIdle` is missing, the extension reports idle. A missing context is fail-open, not proof that a turn is running.

`draft` is `getEditorText()`. A sent transcript clears that editor (`applyTranscript` on `sent`). A turn that has already started has an empty draft and `agentBusy: true` at the same time. That pair is normal.

`speaking` is this session's playback (`session.isSpeaking` or a live `afplay`). It is not `agentBusy`.

`POST /transcript` does not read `agentBusy`. The bridge will accept a prompt while a turn is running. The caller has to refuse. Do not POST while `agentBusy` is true unless the user asked to interrupt that turn.

`POST /barge-in` with `{"abortAgent": true}` calls `ctx.abort()` only when `isIdle()` is false. That cancels a live turn. Do not send it to find out whether a turn exists. `GET /status` already answers that.

## Ready for a new prompt

All of these:

1. `~/.local/state/omp-voice/sessions/<pid>.json` exists and `pid` is alive. The controller deletes a file whose pid is dead. Do that yourself only when `ps -p <pid>` shows nothing.
2. `GET http://127.0.0.1:<port>/status` returns `ok: true`, `version: 2`, and the same `pid`.
3. `agentBusy` is false.
4. The port was read from the registry in this check. `listen(0)` assigns a new port every session start.

`tty` is set once, at listen time, from `/dev/fd/0`. It is stored only when that path starts with `/dev/tty`. Any other stdin, including a pipe, is `null`. The process can still be the foreground job of a shell. Do not restart a session because `tty` is null.

A completed reply is not a field on `/status`. `agentBusy: false` means `isIdle()` was true at that instant. It does not mean the last reply was spoken. Speech readiness is the VoiceBox runbook plus the extension's own playback state.

## This session at 19:46 UTC

| Fact | Value |
|---|---|
| Registry | `sessions/16590.json`, port `62283`, `tty` null, `startedAt` 2026-11-13 19:36:31 UTC |
| `GET /status` | `ok: true`, `version: 2`, `pid: 16590`, `agentBusy: true`, `draftLength: 0`, `speaking: false` |
| Process | pid `16590`, parent zsh pid `6265`, state `R+`, about 3% CPU, up 10 minutes |
| Children | `npm exec @upstash/context7-mcp@2.1.4` pid `16591`, `omp __omp_worker_tiny_inference` pid `16592` |

`isIdle()` returned false. This is not the fail-open path. The process is in the foreground and has a worker and an MCP child. The empty draft means the editor was cleared, not that the turn finished. Do not POST `/transcript`. Do not POST `/barge-in`. Do not kill pid `16590`.

The voice controller's `last_action: cancelled` is the controller, not this OMP turn. It does not cancel the agent.

## Not a recovery

- Writing `agentBusy: false` anywhere. Nothing in the bridge reads a file for that flag.
- POSTing a test prompt to see if the session is stuck.
- Treating port `62283` as stable after this process exits.
