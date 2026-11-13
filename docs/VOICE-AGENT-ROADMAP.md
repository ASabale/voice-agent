# Voice agent roadmap

Status values: `open`, `done`, `blocked`. A `done` row is one verified scenario, not a claim that the product is reliable. Do not lower wake or VAD thresholds to close a row.

## VA-OMP-001 — Status must use the session port

- **Priority:** P0 reliability, found live on 2026-11-13.
- **Problem:** `omp-voice-controller status` always called `http://127.0.0.1:17494/status` and, on connection refused, told the user to restart OMP.
- **Evidence:** Registry pid 80894 answered `/status` on its ephemeral port. Status printed `omp_bridge.ok: false` and a :17494 bind note. After the fix, status reported `ok: true` and `url` equal to the port in `sessions/80894.json`.
- **Approach:** `bridge_status_targets` lists registry ports and adds :17494 only when a process is listening. `probe_bridge_status` tries the delivery port first.
- **Dependencies:** None.
- **Acceptance:** Unit tests in `tests/test_delivery.py`. Live status matches the registry. Spec `docs/testing/scenarios/VA-OMP-001-session-bridge-status.md`.
- **Test method:** `pytest tests/test_delivery.py -q -k "status_targets or probe_"`, then `omp-voice-controller status` against the current registry file.
- **Status:** done 2026-11-13. Do not rerun the spoken A–J rows for this.

## VA-PLAY-001 — Playback state has one owner

- **Priority:** P0. Done in unit tests.
- **Problem:** `extension/voicebox-speech.ts` writes one `~/.local/state/omp-voice/tts-playing.json`. `stopPlayback` sets `playing: false` for whoever calls it. The file has `playing`, `pid`, `started_at` or `ended_at`. It has no session id, turn id, or clip id. A second session can clear the first session's speaking flag. A crash can leave `playing: true` with a dead `afplay` pid. The controller treats that file as "our voice" (`is_voicebox_speaking`).
- **Evidence:** `writeJsonAtomic` is already a rename, so the write itself is atomic. The missing piece is identity and staleness. The 00:48 checkpoint note records the mic hearing VoiceBox and the barge path pausing on that bleed. That is echo, not this row.
- **Approach:** One playback record keyed by session, turn, and clip, with the writer pid and a lease. A clip end from session A must not clear session B. A dead writer must not stay `playing`. Add the failing test before changing the file format the controller reads.
- **Dependencies:** Controller and extension must agree on the new fields in the same change. Do not start the acoustic-echo work in that change.
- **Acceptance:** Two sessions cannot clear each other's playback. A dead writer is not speaking. A finished clip does not end a newer clip.
- **Test method:** Unit test with a temp state directory. No speakers.
- **Status:** done 2026-11-13. Unit tests only. The running OMP process and the running controller still have the old code until they restart. Do not restart them for this row.

## VA-TTS-001 — Speak each chunk once

- **Priority:** P0.
- **Problem:** `enqueue` skips a sentence when `session.spoken` has it or `session.spokenText.includes(sentence)`. A prefix rewrite can drop or replay text. `turn_start` calls `stopPlayback` but does not clear `spoken`, because tool rounds repeat the parent text.
- **Evidence:** Code in `enqueue`, `bargeIn`, and the `turn_start` comment. No new failing fixture this pass.
- **Approach:** Stable message and chunk ids with monotonic sequence numbers. Do not reset spoken state because a prefix changed.
- **Dependencies:** After VA-PLAY-001, or beside it only if the test does not need the new playback file.
- **Acceptance:** Repeated updates do not double-play. A new turn does not keep the old queue. The same sentence in a later turn can still be spoken.
- **Test method:** Unit test on `enqueue` / the speech session. No VoiceBox.
- **Status:** done 2026-11-13 in unit tests. The running OMP process keeps the old extension until that session reloads. Do not restart it for this row.

## VA-AUD-001 — Echo of our own playback

- **Priority:** P0. Not this pass.
- **Problem:** The laptop mic hears the speakers. The checkpoint echo note (00:48) measured that bleed near the level of a conversational stop. There is no AEC. Pausing `afplay` is the current mitigation.
- **Evidence:** Checkpoint section "Echo, 00:48". A barge hold sends SIGSTOP to afplay, which freezes the file, then SIGCONT resumes it. The subtraction index already dropped that stopped time. `refresh_render_reference` still published `render_cursor` from wall time: 8000 samples at 0.50 s, then 12000 after another 0.25 s stopped. The subtraction index stayed at 8000.
- **Approach:** Do not add an AEC library. Stopped time is removed from the file cursor. Forty-eight taps, about 3 ms, sit around the correlation peak. Each tap and their absolute sum must stay within 4, or one scaled copy is removed instead. An overlap of at least 160 samples is scored when the whole block does not fit. The PCM already loaded is kept for 0.6 s after the slot disappears. The delay search scores every sample out to 150 ms. A mono file is linearly resampled onto 16 kHz when it is loaded. The slot records `playback_rate` (0.7 to 2.0). The extension default is 1.18. Each mic block loads the newest speaking slot's WAV. The capture stamp is the ADC block end. A dead `afplay` is skipped. Correlation must be at least 0.75. A weak match is left unchanged. A long room tail is not modelled.
- **Dependencies:** VA-PLAY-001, so the controller knows which clip is ours.
- **Acceptance:** VoiceBox playback alone does not become a user transcript, and a real barge-in still stops playback. Not met.
- **Test method:** Hardware for the echo. `node --experimental-strip-types --test tests/playback-state.test.ts` covers only the WAV description.
- **Status:** open. A paused afplay no longer advances the subtraction index or the published `render_cursor`. Speaker echo is not proven.

## VA-AUD-002 — Dropped microphone frames

- **Priority:** P0.
- **Problem:** The mic callback drops the oldest block when the queue is full (`run_daemon` `on_mic`). Nothing counts the drop.
- **Evidence:** `mic_frames` maxsize 32 in `bin/omp-voice-controller`.
- **Approach:** Count overruns and log them without logging samples.
- **Dependencies:** None.
- **Acceptance:** A full queue increments a counter the status or log can show.
- **Test method:** Unit test around the queue policy if it is extracted. Do not extract it only to test it.
- **Status:** done 2026-11-13 in unit tests. The running controller does not count drops until it is restarted. Do not restart it for this row.

## G10 — Spoken delivery into the OMP draft

- **Priority:** P1. Blocked.
- **Problem:** The old row refused to test delivery because :17494 was down. That reason is obsolete. Delivery itself was not observed in this pass.
- **Evidence:** Checkpoint G10. This pass did not POST `/transcript`.
- **Approach:** Wait until the user asks for a spoken delivery test. Do not restart the session.
- **Dependencies:** VA-OMP-001 done.
- **Acceptance:** One dictated send changes the intended session's draft exactly once.
- **Test method:** Hardware plus the user. Not this loop's next step.
- **Status:** blocked.

## VA-LOG-001 — VoiceBox health is not a per-frame retry

- **Priority:** P0 reliability, found in the controller log on 2026-11-13.
- **Problem:** While VoiceBox did not answer, the idle loop treated that as a Handy mismatch. Every microphone frame opened `http://127.0.0.1:17493/health` and logged `VoiceBox health unread`. The log shows that line from 12:32:16 through 12:32:22.
- **Evidence:** `controller.log` around that minute. `apply_voicebox_model` failure set `_handy_on_light` to the opposite of the Strata flag, so the next frame entered the same branch. A refused connection returns immediately, so the 2 s timeout did not stall the frame. VoiceBox was still not listening on 17493 at 18:54. The marker file said `1.7B`. That is not proof of which model is loaded.
- **Approach:** `sync_speech_tier` keeps the Handy flag on the Strata tier. A refused health check waits 5 s before the next try. A success is not polled again until Strata changes. The refusal is logged once per outage.
- **Dependencies:** None. Do not restart the running controllers to load it.
- **Acceptance:** A failed check does not call health again 80 ms later. A success does not call health on the next frame. A Strata change does.
- **Test method:** `pytest tests/test_speech_tier.py -q`. No Handy restart and no VoiceBox process.
- **Status:** done 2026-11-13 in unit tests. The running controllers keep the per-frame check until they restart. Do not restart them for this row.

## VA-IDLE-001 — A busy Whisper must not drop the idle clip

- **Priority:** P0 reliability, found in the controller log on 2026-11-13.
- **Problem:** The Whisper queue holds one job. An idle utterance that finished while that job was in flight was discarded. The log says `whisper busy; skipped idle utterance` at 12:43:37, 12:52:42, 13:09:13, 13:09:15, and 13:09:23.
- **Evidence:** Those five lines. `kick_whisper` returns false when `whisper_pending` is set, and the idle branch logged and cleared the samples.
- **Approach:** Keep one idle clip. A newer clip replaces the older one. The next idle frame queues it after the in-flight job finishes. Entering dictation drops the held clip so it cannot submit later. The log says `held` or `replaced`. It does not include samples.
- **Dependencies:** None. Do not restart the running controller to load it.
- **Acceptance:** A busy queue keeps the newest idle clip and queues that clip once the worker has taken the previous job. Dictation drops the held clip.
- **Test method:** `pytest tests/test_idle_whisper.py -q`. No microphone and no Whisper model.
- **Status:** done 2026-11-13 in unit tests. The running controller still drops the clip until it restarts. Do not restart it for this row.

## VA-BARGE-001 — A full Whisper queue must not drop the interruption

- **Priority:** P0 reliability. The controller log records `whisper busy; skipped TTS barge clip`, including 2026-11-13 00:15:09 and a run of them on 2026-11-11 from 22:35 through 22:40.
- **Problem:** `kick_whisper` keeps a barge clip when another job is already pending. A full queue with nothing pending returned false, the clip was discarded, and playback resumed.
- **Evidence:** Those log lines. The skip is the `queue.Full` branch. The pending branch already stored `tts_barge_next`.
- **Approach:** A full queue stores that same one clip. A newer clip replaces it. Playback stays paused. `release_barge_clip` queues it once the worker has taken the previous job and `whisper_pending` is clear. The log says `held` instead of `skipped`. It does not include samples.
- **Dependencies:** None. Do not restart the running controller to load it.
- **Acceptance:** A full queue keeps the newest barge clip and queues it after the worker takes the job. Playback is not resumed while that clip is held.
- **Test method:** `pytest tests/test_idle_whisper.py -q`. No microphone and no Whisper model.
- **Status:** done 2026-11-13 in unit tests. The running controller still drops the clip until it restarts. Do not restart it for this row.

## VA-LOG-002 — Speech log stores length, not the sentence

- **Priority:** P1. Found in `speech.log` on 2026-11-13 while VoiceBox was down.
- **Problem:** Every TTS attempt appended the sentence. A refused connection still wrote the words.
- **Evidence:** `speech.log` entries with `event: failed`, `reason` containing `ECONNREFUSED`, and a `text` field. `logSpeech` always stored `text`.
- **Approach:** The record keeps `event`, `chars`, and the extra fields such as `reason`. The sentence is included only when `OMP_VOICE_LOG_TEXT=1`. `controller.log` still quotes transcripts because the spoken checkpoint reads those lines.
- **Dependencies:** None. Do not restart OMP to load it.
- **Acceptance:** A normal record has no `text` field. `chars` is the sentence length. An explicit include puts the sentence back.
- **Test method:** `node --experimental-strip-types --test tests/speech-queue.test.ts`. No VoiceBox.
- **Status:** done 2026-11-13 in unit tests. The running extension keeps the old logger until that session reloads. Do not restart it for this row.

## VA-TTS-002 — A chunk that never played is not spoken

- **Priority:** P0. Found while VoiceBox was down on 2026-11-13.
- **Problem:** `enqueue` adds a chunk to the spoken list before VoiceBox returns audio. A refused request leaves that chunk in the list, so a later copy of the same sentence is skipped even though it was never heard.
- **Evidence:** `speech.log` recorded `event: failed` with `ECONNREFUSED` for those requests. `playTail` ignored a missing clip and did not remove the chunk.
- **Approach:** `noteUnspoken` removes the chunk from the in-flight list. The queue rewinds only when that chunk is still the end of it. A chunk in the middle stays put, so a later sentence is not spoken twice. A chunk that already played stays spoken.
- **Dependencies:** VA-TTS-001. Do not restart OMP to load it.
- **Acceptance:** After a failed chunk, that sentence is not spoken-already. The following sentence remains spoken-already. A failed tail rewinds the queue to empty. A played sentence is not forgotten.
- **Test method:** `node --experimental-strip-types --test tests/speech-queue.test.ts`. No VoiceBox.
- **Status:** done 2026-11-13 in unit tests. The running extension keeps the old queue until that session reloads. Do not restart it for this row.

## VA-LOG-003 — Logs keep one backup after 1 MiB

- **Priority:** P1. Measured on 2026-11-13.
- **Problem:** `controller.log` was 3.1 MiB and `speech.log` was 1.5 MiB. Neither file was rotated. The controller process holds `controller.log` open, so renaming it while that process runs would make new lines land in the renamed file.
- **Evidence:** Those sizes. `log()` only prints. The start path opens `controller.log` in append mode and never checks the length. `logSpeech` appended forever.
- **Approach:** `rotate_log` and `rotateLogFile` keep one `.1` backup when the file is larger than 1 MiB. The controller start path rotates before it opens the file. `logSpeech` rotates before it appends. This pass did not rename the live files.
- **Dependencies:** None. Do not restart the controller or OMP to load it.
- **Acceptance:** A file over the limit becomes the `.1` backup, and a second rotation replaces that backup. A small file and a missing file stay put.
- **Test method:** `pytest tests/test_speech_tier.py -q` and `node --experimental-strip-types --test tests/speech-queue.test.ts`. Temp files only.
- **Status:** done 2026-11-13 in unit tests. The running controller and extension keep growing the current files until they restart. Do not restart them for this row.

## VA-TTS-003 — A player error is not spoken

- **Priority:** P0. Same rule as VA-TTS-002.
- **Problem:** `play` marked the chunk spoken when `afplay` closed, including a non-zero exit and a spawn error. A kill signal also closes the process, and that one did start.
- **Evidence:** `child.on("error")` and `child.on("close")` both resolved the same completion, and the next line always called `commitSpoken`. No afplay failure was in today's log. VoiceBox is down, so playback was not reached.
- **Approach:** `playbackHeard` is false for a spawn error or a non-zero exit with no signal. A signal, including the 45 s watchdog kill, counts as started. A miss calls `releaseUnspoken`. A hit calls `commitSpoken`.
- **Dependencies:** VA-TTS-002. Do not restart OMP to load it.
- **Acceptance:** Exit 0 is heard. Exit 1 is not. `SIGKILL` is heard. A spawn error is not.
- **Test method:** `node --experimental-strip-types --test tests/speech-queue.test.ts`. No afplay and no VoiceBox.
- **Status:** done 2026-11-13 in unit tests. The running extension keeps the old completion until that session reloads. Do not restart it for this row.

## VA-OMP-003 — A missing registry file still has a listen port

- **Priority:** P0. Found live at 14:16 on 2026-11-13.
- **Problem:** Pid 80894 was the focused Terminal session, but `sessions/` had no file for it. Delivery was `paste` with `port=None`, so live partials were skipped. The process was listening on `127.0.0.1:56876`, and `GET /status` there returned `ok: true` and `pid: 80894`.
- **Evidence:** Controller log `Delivery paste pid=80894 port=None focused_text=True` and `Partial field skipped (paste, focused=True)`. The status read above. A session object that still has no port stays a paste.
- **Approach:** When the registry port is missing, `lsof -F n` must show one `127.0.0.1` listen port, and that port's `/status` must name the same pid. Two ports, or a status pid that does not match, stays a paste.
- **Dependencies:** VA-OMP-001. Do not restart the controller to load it. Do not POST `/transcript`.
- **Acceptance:** A focused omp tab whose only loopback listener answers `/status` for that pid is a bridge. Without that port, it is still a paste.
- **Test method:** `pytest tests/test_delivery.py -q`. The test does not call lsof or the live bridge.
- **Status:** done 2026-11-13 in unit tests. The running controller still pastes until it restarts. Do not restart it for this row.

## VA-TTS-004 — A refused VoiceBox is not called again for 5 s

- **Priority:** P1. Measured at 19:22 on 2026-11-13.
- **Problem:** `generate` calls VoiceBox for every sentence. While port 17493 is closed, each sentence opens a connection and writes a `failed` line. Fourteen of those lines landed in the 19:22 minute.
- **Evidence:** `speech.log` records at `2026-11-13T19:22`, including four between 19:22:06 and 19:22:07, each with `ECONNREFUSED`.
- **Approach:** `isConnectionRefusal` covers that error and its `cause`. The next `generate` returns before `fetch` until 5 seconds after the refusal. A held call logs once. A clip that is produced clears the hold. An HTTP error does not start it.
- **Dependencies:** VA-TTS-002. Do not restart OMP to load it. Do not start VoiceBox.
- **Acceptance:** A time before the retry instant is held. The retry instant is not. `ECONNREFUSED`, including a cause, is a refusal. `http 500` is not.
- **Test method:** `node --experimental-strip-types --test tests/speech-queue.test.ts`. No socket.
- **Status:** done 2026-11-13 in unit tests. The running extension still connects for every sentence until that session reloads. Do not restart it for this row.

## Later

Command semantics, a spoken-output contract, and splitting the controller stay behind the open P0 row. `controller.log` still quotes transcripts because the spoken checkpoint reads those lines. Do not refactor the controller while VA-AUD-001 is open.
