# Voice agent architecture

Checked against `bin/omp-voice-controller` and `extension/voicebox-speech.ts` on 2026-11-13. The README diagram used to pin the bridge at port 17494. That sentence is updated. This file is the one to follow when they disagree.

## Processes

| Piece | Role | Boundary |
|---|---|---|
| `omp-voice-controller` | Mic, wake, VAD, Handy start/stop, command outcomes, focus routing | Python process. State under `~/.local/state/omp-voice/` |
| Handy | Local speech to text | Separate app. The controller watches its history database |
| OMP plus `extension/voicebox-speech.ts` | Draft, submit, VoiceBox playback | One extension inside each OMP session |
| VoiceBox | Cloned-voice HTTP TTS | Separate app. The extension calls `http://127.0.0.1:17493` |

The controller does not speak. The extension does not read the microphone.

## Bridge

Each OMP session listens on `127.0.0.1` with port 0 and writes `~/.local/state/omp-voice/sessions/<pid>.json`:

```json
{"pid": 0, "port": 0, "tty": null, "startedAt": 0}
```

`tty` in the file may be null. `omp_session_records` fills it from `lsof` when it can. A live omp pid with no registry port uses its one `127.0.0.1` listen port when `GET /status` on that port returns `ok` and the same pid. Two listen ports stay unset. `load_session_registry` drops a file whose pid is dead.

`choose_delivery` sends to that session's port when the focused text control's tty matches one session, or when focus is not text and the newest session has a port. Any other text control is a paste into the focused field. Port 17494 is used only when `lsof` shows a listener and that listener's pid is the chosen session (`legacy_bridge_owner_pid`).

`GET /status` returns `ok`, `version`, `pid`, `speaking`, `agentBusy`, `draft`, `draftLength`. `POST /transcript` and `POST /barge-in` are the write paths. Status must not call them.

`bridge_status_targets` is the list status and barge-in fan-out use. It does not add :17494 when nobody is listening.

## Playback

Each OMP session writes only `~/.local/state/omp-voice/tts-playing/<pid>.json`. The slot has `playing`, `turn`, `clip`, `writer_pid`, `afplay_pid`, `started_at`, `lease_until`, and `reason` (`begin` or `end`). A newer turn or clip is not replaced by an older end. The flat `tts-playing.json` is rewritten from every slot as a projection for an old controller: `playing: true` while any slot is playing, otherwise `playing: false` and the latest `ended_at`.

While a clip is playing, the slot's `reference` is the WAV file `afplay` was given: sample rate, channel count, frame count, and path. `wavReference` accepts 16-bit PCM only. Ending the clip removes `reference`, and the WAV file is deleted when `afplay` exits. The controller keeps the PCM it already loaded for 0.6 s after the slot disappears, so the acoustic tail of that clip can still be subtracted. It does not read the deleted file. Each microphone block reloads that file when the clip identity changes. The clip is the newest slot that is still speaking: a later `started_at` wins over an earlier file, and a dead `afplay` is not used. The PCM is kept only when the header matches that slot. About once a second, `status.json` records `render_connected`, `render_rate`, `render_frames`, `render_processed_frames`, `render_cursor`, and `render_aligned`. `render_cursor` counts 16 kHz grid samples, the positions both cancellers read, not samples in the file's own rate. `render_aligned` is true when a mono file has been mapped onto the 16 kHz microphone grid. The playback WAVs left in `/tmp` are 22050 Hz mono 16-bit, so a file is resampled with linear interpolation when its rate is not 16000. Multi-channel files are averaged onto mono before that resampling. The map is not band-limited. The microphone callback stamps the wall time when the ADC block ended. PortAudio's `currentTime` minus that block's end is how late the callback ran, and that lateness is removed. A missing clock keeps the callback's wall time. `apply_render_subtraction` uses that stamp and the slot's `playback_rate`. `afplay -r` consumes that many seconds of the file per wall-clock second. The extension default is 1.18. Time spent stopped with SIGSTOP does not advance the file. `render_cursor` uses that same stopped time, counted on the 16 kHz grid. A missing rate means 1x. Time the block spends in the queue does not move it. A microphone block that starts before the file, or runs past its end, is scored on the overlapping samples when that overlap is at least 160. The samples outside the file are left as recorded. A shorter overlap is ignored unless the whole block fits inside the file. The search scores every sample out to 150 ms. Correlation must be at least 0.75. Forty-eight taps sit around the correlation peak, about 1.5 ms before it and 1.5 ms after it, because that peak is not always the first arrival. Each tap is at most 4, and the taps together are at most 4. A fit outside that range falls back to one scaled copy. The logged delay is that acoustic lag, not the length of the block. A weaker match is not changed. This is not a room model, and the log line does not include samples. The new controller treats the `tts-playing` directory as the only source when that directory exists, including when it is empty. A slot is speaking when:

- it has ended and `ended_at` is inside 0.6s, or
- it is playing, its `afplay` pid is alive, and a dead writer is still inside 60s of `started_at`, or
- it is playing with no `afplay` pid, the writer is alive, and `now < lease_until`.

A dead `afplay` is not speaking. A legacy file with no `sessions` object still means "playing" without a pid check, and only when the directory is absent.

The running controller and the running OMP process keep the previous code until they restart. This pass did not restart them.

## Speech queue

`enqueue` speaks a chunk unless `isSpokenChunk` says it is an exact chunk already queued or several consecutive chunks joined in order. A longer sentence that starts with the last spoken chunk, even when an earlier sentence is already queued, speaks only the new tail, so "I will leave" is not said again inside "I will leave the player." A shorter sentence that only occurs inside an older chunk is still spoken. The first short sentence waits for the next sentence or the end of the message. Speaking it immediately was the replay. A prefix rewrite realigns with `queuedAfterRewrite` and does not clear the chunk list. Clearing that list was what replayed the reply.

A connection refusal holds the next VoiceBox request for 5 seconds. A chunk that VoiceBox does not return, or whose player exits non-zero without a signal, is removed from the in-flight list and is not treated as spoken. A kill signal counts as started. The queued cursor moves back only when that chunk is still the end of the queue, so an earlier failure does not replay a later sentence. The running extension keeps a failed chunk in the list until that session reloads.

A different assistant message `id` stops playback only when its text does not continue the reply already playing. A new id whose words extend or prefix that reply leaves the clip and the chunk list alone. The period in "I will leave." does not make "I will leave the player." a different reply. A genuinely different reply still stops playback, clears the chunk list, and can speak a sentence again. The same message id, including a tool round that sends the parent text again, keeps the chunks. `turn_start` does not stop audio. Stopping there aborted the clip, dropped the queue, and the same sentences played again. A user interrupt still calls `bargeIn`. There is no speaker proof until the OMP session reloads this extension. `speech.log` and `controller.log` keep one `.1` backup after 1 MiB. The controller rotates only when a new process opens the file, because the running process already holds it. `speech.log` records `event`, `chars`, and the failure reason. It does not record the sentence unless `OMP_VOICE_LOG_TEXT=1`. The running extension still writes the sentence until that session reloads. `controller.log` still quotes transcripts because the spoken checkpoint reads those lines.

## Audio path

The idle loop calls `sync_speech_tier` once per frame. Handy follows the Strata tier. VoiceBox is asked again 5 s after a refused health check, not on the next frame, and a success is left alone until Strata changes. A refusal does not change the Handy flag. The running controllers keep the old per-frame check until they restart.

The controller opens the default input with sounddevice, 16 kHz mono int16, queue max 32. `offer_mic_frame` drops the oldest block when the queue is full and counts that loss. A PortAudio input overflow, underflow, or status string counts as invalid. The totals are `mic_dropped` and `mic_invalid` on `status.json`. The log line is `mic capture dropped=N invalid=M` and does not include samples. The running controller keeps the old callback until it restarts. Wake and dictation run on the frames that were kept. The Whisper queue holds one job. An idle clip that arrives while that job is in flight is kept, and a newer idle clip replaces it. The next idle frame queues the kept clip. Entering dictation drops it. The log line is `whisper busy; held idle utterance` or `replaced`. The running controller still drops that clip until it restarts. A barge clip that finds the queue full is kept the same way. Playback stays paused, and `release_barge_clip` queues it once the worker has taken the previous job. The log line is `whisper busy; held TTS barge clip`. During our playback a hearing that is not yet "stop" does not pause the `omp-vb-` `afplay`. A transcript that is not "stop" does not resume it either. An empty hold, a skipped Whisper job, and a rejected clip clear the hold and do not resume it. The resume that runs after playback has already ended stays. Only a confirmed stop calls `stop_playback`. `cancel_playback_echo` runs before VAD. When the playback reference is aligned and `aec-audio-processing` imports, that is WebRTC echo control on 10 ms frames from the same cursor, and the 48-tap fit is not applied to that block. A missing module falls back to the fit. No reference leaves the block unchanged. The running controller keeps the old call until it restarts. This is not a measured room cancellation. See `docs/testing/AEC-DECISION.md`.

## What is not owned yet

- A room measurement of the WebRTC canceller. The synthetic path is in `cancel_playback_echo`. The microphone trial is not.
