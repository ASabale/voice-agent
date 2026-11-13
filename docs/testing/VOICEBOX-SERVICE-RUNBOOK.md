# VoiceBox service runbook

Checked 2026-11-13 19:40 UTC, rechecked 19:45 UTC. Same processes. VoiceBox.app `0.5.0`, bundle id `sh.voicebox.app`. Re-read every pid and port before acting. Do not reuse the numbers below as if they were still true.

A GUI process, a server process, a listening socket, and an HTTP response are four different facts. Record each one.

## What is installed

| Piece | Path | Role |
|---|---|---|
| GUI | `/Applications/Voicebox.app/Contents/MacOS/voicebox` | Owns the server lifecycle. `CFBundleShortVersionString` is `0.5.0`. |
| Server | `/Applications/Voicebox.app/Contents/MacOS/voicebox-server` | PyInstaller sidecar. This is the process that must listen. |
| MCP helper | `/Applications/Voicebox.app/Contents/MacOS/voicebox-mcp` | Not the TTS server. |
| Data | `~/Library/Application Support/sh.voicebox.app` | SQLite `voicebox.db`, profiles, generations. |
| Keep-running sentinel | `~/Library/Application Support/sh.voicebox.app/.keep-running` | One byte, ASCII `1`. Created 2026-11-06 23:12 EST. Rewritten 2026-11-13 10:12:06 EST. |
| LaunchAgent | none for VoiceBox | The GUI is not restarted by launchd. |

There is no LaunchDaemon. The CUDA backend directory exists and is empty. The GUI binary says it falls back to the bundled CPU binary when no CUDA backend is present. On this Mac the server still loads MLX (`libmlx.dylib`) and talks to Metal.

## How the GUI starts the server

Source of the procedure: [jamiepine/voicebox](https://github.com/jamiepine/voicebox) tag `v0.5.0`, which is the installed `CFBundleShortVersionString`. The files are `tauri/src-tauri/src/main.rs`, `app/src/App.tsx`, and `backend/server.py`.

`SERVER_PORT` is `17493`. `LEGACY_PORT` is `8000`. The Python default in `backend/server.py` is also `8000`, but the GUI overrides it.

On a production launch the window calls `start_server` once. The sidecar arguments are:

```text
--data-dir <app data dir> --port 17493 --parent-pid <gui pid>
```

`--host 0.0.0.0` is added only when network access is enabled. `VOICEBOX_MODELS_DIR` is set only when a custom models directory is set. The data dir on this Mac is `~/Library/Application Support/sh.voicebox.app`.

If that one start fails for a reason other than "port in use", the UI records the error and does not try again. It polls `/health` only when the port is already taken. A server that exits after launch is not started again by the running GUI.

`restart_server` stops the sidecar, waits 1 second, and calls `start_server`. The visible **Restart** button (`settings.gpu.switchToCuda.button`) is the CUDA switch. `backends/cuda` on this Mac is empty, so that button is not a general recovery control. Model-folder changes also call `restart_server`. Neither is the path for a crashed server.

Do not exec `voicebox-server` from a test or a loop. The GUI also kills an orphaned `voicebox-server` it finds on legacy port `8000`. A hand-built process is not the supported server.

Dev mode skips the auto-start and tells you to run the server yourself. This install is the production app. Do not clone another VoiceBox.

## Expected process and port

After a successful GUI start:

1. `ps` shows `MacOS/voicebox` and a child `MacOS/voicebox-server`. The 2026-11-13 10:12 launch used two server pids: parent server `29308` (parent GUI `29277`) and child server `29328`.
2. `lsof -nP -iTCP:17493 -sTCP:LISTEN` shows `voicebox-server` on `127.0.0.1:17493`. If something else owns the port, stop and record that pid. Do not kill it from this runbook.
3. One request: `curl -fsS -m 2 http://127.0.0.1:17493/health`. Record the status code and the body. A refused connection is not a health payload.
4. `curl -fsS -m 2 http://127.0.0.1:17493/profiles`. The profile this loop speaks is the name in `~/.local/state/omp-voice/profile` (currently `Akshay`, with a trailing newline). Names present in `voicebox.db` on this Mac: `Akshay` (`4bde1e0f-bddd-40cf-9ab1-4b34632b51fd`), `Akshay hindi` (`892f327a-45a6-4cad-be98-ec7bad6e634b`), `kishu` (`920fac92-21f6-4518-aa9a-0b4efa5a07b6`). A row in SQLite is not a loaded profile. Only the HTTP list is.

Do not POST `/generate` or `/generate/stream` until those two GETs succeed. A WAV from an earlier day under `generations/` is not a new generation.

## Shutdown

The supported stop is the GUI command `stop_server`. An agent does not kill the GUI. An agent does not `kill` a `voicebox-server` pid that the GUI just spawned. Identify the listener with `lsof` and leave it alone unless a later runbook revision says otherwise.

## Recovered at 19:49 UTC

A person opened VoiceBox again. GUI pid `20266`. Listener pid `20305` on `127.0.0.1:17493`, arguments `--data-dir ~/Library/Application Support/sh.voicebox.app --port 17493 --parent-pid 20266`. Parent server pid `20286` is the same command and is not the listener.

`GET /health` returned 200: `healthy`, `model_loaded` true, `model_size` `1.7B`, `backend_type` `mlx`, `gpu_type` `MPS (Apple Silicon)`. The first probe, about 25 seconds after launch, timed out. The next one returned in 6 ms.

`GET /profiles` returned `Akshay`, `Akshay hindi`, and `kishu`. One `POST /generate/stream` used `Akshay` (`4bde1e0f-bddd-40cf-9ab1-4b34632b51fd`), text `Voicebox is ready.`, `model_size` `1.7B`. Response 200, `audio/wav`, 96044 bytes, 24 kHz, mono, 16-bit, 2.00 s, RMS about 3277, peak about -4.5 dBFS. `afplay` exited 0. Output volume was 19 and was not changed. The server was still listening afterward. No evening crash report.

That is generation and a finished player. It is not a person confirming the speaker, and it is not VA-INT-001.

## What was true at 19:40 UTC

| Check | Result |
|---|---|
| GUI | pid `29277`, parent pid `1`, command `MacOS/voicebox`, up about 4.5 h. Not killed. |
| Server | no `voicebox-server` process |
| Port 17493 | no listener. `curl` to `/health` returned connection refused (`curl` exit 7). |
| OMP | pid `16590`, registry `~/.local/state/omp-voice/sessions/16590.json` port `62283`, `tty` null. `GET /status` returned `ok: true`, `version: 2`, `agentBusy: true`, `draftLength: 0`, `speaking: false`. No POST. |
| Local LLM | no Strata and no MTPLX process. `memory_pressure -Q` reported 94% free. That does not explain the crashes below. |

`tty: null` on this session file is the value the extension wrote at start (`startedAt` 2026-11-13 19:36:31 UTC). It is not, by itself, a broken bridge. `agentBusy: true` with an empty draft means the session is not idle. Do not submit a prompt to it.

## Crashes already on disk

All three are MLX Metal failures. The GUI that is still running spawned a server once and did not spawn another.

| Local time | Signal | Server pid | GUI parent | Lifetime | Fault |
|---|---|---|---|---|---|
| 08:57:35 | `SIGABRT` | 75213 | voicebox 75181 | since 2026-11-10 18:14:38 | `abort() called` from `mlx::core::gpu::check_error(MTL::CommandBuffer*)`. Report `voicebox-server-2026-11-13-085736.ips`. |
| 10:08:44 | `SIGABRT` | 7303 | voicebox 7271 | since 09:03:57 the same morning | Same `check_error` abort. Report `voicebox-server-2026-11-13-100845.ips`. |
| 10:12:46 | `SIGSEGV` | 29328, parent server 29308 | voicebox 29277 | 38 s (launch 10:12:08) | `EXC_BAD_ACCESS` at address `0x8` in `mlx::core::eval_impl`, during `mlx::core::metal::MetalAllocator::malloc`. Report `voicebox-server-2026-11-13-101246.ips`. |

Reports live in `~/Library/Logs/DiagnosticReports/`. The 08:57 process had been up for days, so this is not only a startup out-of-memory failure.

## Keep-running sentinel

The GUI writes `.keep-running` only inside `RunEvent::Exit`, and only when **Keep server running when app closes** is on (`set_keep_server_running`). The write is the byte `1`. It then POSTs `http://127.0.0.1:17493/watchdog/disable`.

The server watches `--parent-pid`. When that pid dies it waits a grace period. It stays up if the disable request arrived or the sentinel is present. Otherwise it exits. The default of the setting in code is off. The file on disk means some earlier exit had it on.

The watchdog removes a stale sentinel after the server is fully ready. There is no `watchdog.log` under the data dir, so the 10:12 server never got that far. The sentinel's mtime is 10:12:06 EST, and the server pid `29308` was launched at 10:12:08. The file is the previous exit, not a request to start a new server. Leaving it in place does not make the current GUI spawn anything.

## Recovery

1. Read `~/.local/state/omp-voice/sessions/*.json` and `GET /status`. If `agentBusy` is true, do not POST `/transcript`.
2. If `voicebox-server` is running and `17493` is listening, do one `/health` GET and stop if it fails. Do not start a second server.
3. If the GUI is up and the server is absent, do not exec the sidecar and do not `open` the app again. This GUI already ran its one production start.
4. Human action: quit VoiceBox and open it again. Production mode calls `start_server` once on launch. That is the supported start. An agent does not quit or kill the GUI.
5. After the window is back, check for a `voicebox-server` child, then one `curl -fsS -m 2 http://127.0.0.1:17493/health`, then `GET /profiles`.
6. If the new server exits, read the newest `voicebox-server-*.ips` and stop. The last three lifetimes died in MLX Metal (`check_error` or `eval_impl`). Another launch from an agent is not authorized while that is still the fault.

## Not a recovery

- Polling `/health` in a loop. It stays refused until a server listens.
- Treating the GUI pid as proof that speech works.
- Launching `voicebox-server` by hand, including with `--port 17493`.
- Killing pid `29277` from an agent.
- Reading `.keep-running` as "start the server".
- Clicking the GPU **Restart** button. It is the CUDA switch, and `backends/cuda` is empty.
