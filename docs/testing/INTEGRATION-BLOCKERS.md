# Integration blockers

Newest first. `BLOCKED` is not a pass. Re-check processes before trusting a pid in this file.

## 2026-11-14 04:15 UTC — the canceller now reports its own residual

**Status:** PASS for VA-OBS-001 at LEVEL 1. `cancel_playback_echo` accumulates raw and cleaned energy per block (silent references skipped) and `publish_capture_totals` writes `aec_echo_db` and `aec_blocks` into `status.json`. Measured -33.1 dB over the 8 s four-path room feed, 101 blocks. A latent bug surfaced on the way: int16 energies overflowed in `np.dot`, so the widening to int64 is now asserted by the test. Full controller suite: 215 passed. Pid 64238 was not restarted, so the live status file still lacks these fields until the new code runs. Not a room measurement, not VA-INT-001. See `docs/testing/scenarios/VA-OBS-001-aec-residual.md`.

## 2026-11-14 03:52 UTC — four arrivals at once are cancelled in the synthetic room

**Status:** PASS for VA-AEC-004 at LEVEL 1. A mic signal built from the played clip at 15/30/60/90 ms with gains 0.45/0.18/0.07/0.03, fed through `cancel_playback_echo` in production 1280-sample blocks, loses 37.7 dB of echo tail. Near-end speech layered on top keeps 0.54 of its energy. After a 20 s run the tail is still 38.7 dB down. Full controller suite: 213 passed. Pid 64238 was not restarted and still owns the microphone, so the live path keeps the old filter and this is not a room measurement. Not VA-INT-001. See `docs/testing/scenarios/VA-AEC-004-multi-path-room.md`.

## 2026-11-14 00:04 UTC — the status cursor now matches the canceller's grid

**Status:** PASS for VA-AEC-003 at LEVEL 1. `render_cursor` counted file samples while both cancellation paths indexed the resampled 16 kHz reference; a 24 kHz clip published 1.5x the true position. The cursor now counts grid samples, clamps to `render_processed_frames`, and still freezes across SIGSTOP. Full controller suite: 210 passed. Pid 64238 was not restarted and still runs the old path, so `status.json` from the live process keeps the old units until it reloads. Not a speaker test and not VA-INT-001.

## 2026-11-13 23:45 UTC — stereo render references are downmixed, room still unmeasured

**Status:** PASS for VA-AEC-002 at LEVEL 1. A stereo WAV now averages to a 16 kHz mono reference instead of skipping AEC; a planted 20 ms echo through `cancel_playback_echo` lost at least 12 dB on a synthetic 24 kHz stereo clip. Two stale contract tests in `tests/test_command_semantics.py` and `tests/test_handy_file_phrases.py` still expected a non-stop barge to resume the clip; they now assert no resume, matching VA-TTS-008. Full controller suite: 208 passed. Pid 64238 was not restarted and still owns the microphone, so this is not a room result and not VA-INT-001.

## 2026-11-13 23:32 UTC — a later sentence does not repeat its spoken opening

**Status:** PASS for VA-TTS-012 at LEVEL 4. When an earlier sentence is already queued, a longer sentence that starts with the last chunk speaks only the new words. At 23:31:01 the running session aborted a 151-character request and dropped the queue with reason `epoch`. Pid 16590 was not reloaded. This is not the microphone.

## 2026-11-13 23:29 UTC — a period does not make a growing sentence a new reply

**Status:** PASS for VA-TTS-011 at LEVEL 4. A new message id whose words grow from `I will leave.` to `I will leave the player.` does not stop playback. A different sentence still does. At 23:27:51 the running session requested 138 characters, aborted at 23:27:53, and dropped the queue. That process was not reloaded. This is not the microphone.

## 2026-11-13 23:27 UTC — an unconfirmed barge does not resume the clip

**Status:** PASS for VA-TTS-010 at LEVEL 1. An empty hold, a skipped Whisper job, and a rejected clip clear the hold and do not call `resume_tts_clips`. Playback that has already ended still resumes once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 04:16 UTC — a growing sentence does not repeat its opening

**Status:** PASS for VA-TTS-009 at LEVEL 4. A sentence that grows from `I will leave.` to `I will leave the player.` speaks only the new words. The first short sentence is not spoken before the next sentence or the end of the message. Pid 16590 was not reloaded. This is not the microphone.

## 2026-11-14 04:10 UTC — a non-stop transcript does not resume the clip

**Status:** PASS for VA-TTS-008 at LEVEL 1. Whisper hearing `Thank you.` does not call `resume_tts_clips`. The hold is cleared. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 04:04 UTC — a hearing does not pause the clip

**Status:** PASS for VA-TTS-007 at LEVEL 1. A barge hold no longer sends `SIGSTOP` to the playing clip. A confirmed stop still stops playback. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:58 UTC — a continued reply keeps the clip

**Status:** PASS for VA-TTS-006 at LEVEL 4. A new message id whose text continues the playing reply does not stop playback. A different reply still does. Pid 16590 was not reloaded. This is not the microphone.

## 2026-11-14 03:52 UTC — a turn start no longer aborts speech

**Status:** PASS for VA-TTS-005 at LEVEL 4. `turn_start` does not bump the speech epoch or drop the queue. `stopPlayback` still does. Pid 16590 was not reloaded. This is not the microphone.

## 2026-11-14 03:46 UTC — a newer row after a clear is dispatched once

**Status:** PASS for VA-DELIV-048 at LEVEL 1. A silence flush that returns `cleared` leaves the consumed id. The next frame dispatches the later row once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:40 UTC — a newer row after a scratch is dispatched once

**Status:** PASS for VA-DELIV-047 at LEVEL 1. A silence flush that returns `scratched` leaves the consumed id. The next frame dispatches the later row once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:34 UTC — a newer row after a flush is dispatched once

**Status:** PASS for VA-DELIV-046 at LEVEL 1. A silence flush that consumes row 8 does not mark a later row 9 as seen. The next frame dispatches `Next line.` once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:28 UTC — an older history read does not repeat a clear

**Status:** PASS for VA-DELIV-045 at LEVEL 1. A silence flush that returns `cleared` keeps the consumed history id when the next read is older. The same row is not dispatched again. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:22 UTC — an older history read does not repeat a scratch

**Status:** PASS for VA-DELIV-044 at LEVEL 1. A silence flush that returns `scratched` keeps the consumed history id when the next read is older. The same row is not dispatched again. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:16 UTC — an older history read keeps the consumed flush row

**Status:** PASS for VA-DELIV-043 at LEVEL 1. After a silence flush consumes row 8, a later read of id 0 does not replace it. The next frame does not dispatch that row again. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:10 UTC — an appended flush records appended

**Status:** PASS for VA-DELIV-042 at LEVEL 1. A silence flush that returns `appended` stays DICTATING and records `last_action` as `appended`. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 03:04 UTC — a held flush records held

**Status:** PASS for VA-DELIV-041 at LEVEL 1. A silence flush that returns `held` records `last_action` as `held`. It stays DICTATING. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:58 UTC — a held send flush stays dictating

**Status:** PASS for VA-DELIV-040 at LEVEL 1. A silence flush that returns `held` stays DICTATING, starts Handy once, and does not type. `Ship the notes.` and `ship please` stay held. The status action is still recorded as `appended`. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:52 UTC — a held send row stays dictating

**Status:** PASS for VA-DELIV-039 at LEVEL 1. A new Handy row that returns `held` stays DICTATING, starts Handy once, and does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:46 UTC — a cancel row plays the cancel cue

**Status:** PASS for VA-DELIV-038 at LEVEL 1. A new Handy row whose dispatch returns `cancelled` plays the cancel cue and goes to IDLE. A pause row still plays the pause cue. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:40 UTC — a cancel row stays idle

**Status:** PASS for VA-DELIV-037 at LEVEL 1. A new Handy row whose dispatch returns `cancelled` goes to IDLE and does not start Handy. The row path still plays the pause cue. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:34 UTC — a cancelled flush stays idle

**Status:** PASS for VA-DELIV-036 at LEVEL 1. A silence flush that returns `cancelled` goes to IDLE and does not start Handy. The stop toggle still runs once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:28 UTC — a failed cancel post stays cancelled

**Status:** PASS for VA-DELIV-035 at LEVEL 1. A transcript POST that fails on `cancel` returns `cancelled`, does not type, and leaves `Ship the notes.` and `ship please` held. A failed scratch still returns `held`. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:22 UTC — a dead status does not type cancel

**Status:** PASS for VA-DELIV-034 at LEVEL 1. While `Ship the notes.` and `ship please` are held, a status GET that fails on `cancel` does not type and leaves both held. The return stays `cancelled`. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:16 UTC — a v1 cancel leaves both prefixes

**Status:** PASS for VA-DELIV-033 at LEVEL 1. On a v1 bridge, `cancel` posts only that command and leaves `Ship the notes.` and `ship please` held. The next `all done` posts them once. Nothing is typed. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:10 UTC — a failed v1 cancel post keeps both holds

**Status:** PASS for VA-DELIV-032 at LEVEL 1. On a v1 bridge, a transcript POST that fails on `cancel` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 02:04 UTC — a failed v2 cancel post keeps both holds

**Status:** PASS for VA-DELIV-031 at LEVEL 1. On a v2 bridge, a transcript POST that fails on `cancel` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:58 UTC — cancel leaves both prefixes

**Status:** PASS for VA-DELIV-030 at LEVEL 1. On a v2 bridge, `cancel` posts only that command and leaves `Ship the notes.` and `ship please` held. The next `all done` posts them once. Nothing is typed. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:52 UTC — a v1 clear drops the saved pause line

**Status:** PASS for VA-DELIV-029 at LEVEL 1. On a v1 bridge, `please stop` then a successful `clear draft` leaves no pause line. The next `all done` posts `send prompt` only. Nothing is typed. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:46 UTC — a failed v1 clear keeps the pause line

**Status:** PASS for VA-DELIV-028 at LEVEL 1. On a v1 bridge, after `please stop`, a `clear draft` POST that fails leaves `please` saved. The next `all done` posts `Ship the notes. ship please send prompt` once. Nothing is typed. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:40 UTC — a failed clear keeps the pause line

**Status:** PASS for VA-DELIV-027 at LEVEL 1. On a v2 bridge, after `please stop`, a `clear draft` POST that fails leaves `please` saved. The next `all done` posts `Ship the notes. ship please send prompt` once. Nothing is typed. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:34 UTC — a clear drops the saved pause line

**Status:** PASS for VA-DELIV-026 at LEVEL 1. On a v2 bridge, `please stop` then a successful `clear draft` leaves no pause line. The next `all done` posts `send prompt` only. Nothing is typed. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:28 UTC — a successful v1 clear drops both holds

**Status:** PASS for VA-DELIV-025 at LEVEL 1. On a v1 bridge, `clear draft` posts only that command and clears `Ship the notes.` and `ship please`. Nothing is typed. The next `all done` posts `send prompt` only. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:22 UTC — a successful v2 clear drops both holds

**Status:** PASS for VA-DELIV-024 at LEVEL 1. On a v2 bridge, `clear draft` posts only that command and clears `Ship the notes.` and `ship please`. Nothing is typed. The next `all done` posts `send prompt` only. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:16 UTC — a failed v1 clear post keeps both holds

**Status:** PASS for VA-DELIV-023 at LEVEL 1. On a v1 bridge, a transcript POST that fails on `clear draft` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:10 UTC — a failed v2 clear post keeps both holds

**Status:** PASS for VA-DELIV-022 at LEVEL 1. On a v2 bridge, a transcript POST that fails on `clear draft` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 01:04 UTC — a failed v1 scratch post keeps both holds

**Status:** PASS for VA-DELIV-021 at LEVEL 1. On a v1 bridge, a transcript POST that fails on `scratch that` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:58 UTC — a failed v2 scratch post keeps both holds

**Status:** PASS for VA-DELIV-020 at LEVEL 1. On a v2 bridge, a transcript POST that fails on `scratch that` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:52 UTC — a failed v2 pause post keeps both holds

**Status:** PASS for VA-DELIV-019 at LEVEL 1. On a v2 bridge, a transcript POST that fails on `please stop` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:46 UTC — a failed v1 pause post keeps both holds

**Status:** PASS for VA-DELIV-018 at LEVEL 1. On a v1 bridge, a transcript POST that fails on `please stop` does not type. `Ship the notes.` and `ship please` stay held. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:40 UTC — a v1 pause leaves both prefixes

**Status:** PASS for VA-DELIV-017 at LEVEL 1. On a v1 bridge, `please stop` posts `please pause listening` only and leaves `Ship the notes.` and `ship please` held. The next `all done` posts `Ship the notes. ship please send prompt` once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:34 UTC — pause leaves both prefixes

**Status:** PASS for VA-DELIV-016 at LEVEL 1. While `Ship the notes.` and `ship please` are held, `please stop` posts only that command and does not type. Both stays held. The next `all done` posts `Ship the notes. ship please send prompt` once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:28 UTC — scratch leaves both prefixes

**Status:** PASS for VA-DELIV-015 at LEVEL 1. While `Ship the notes.` and `ship please` are held, `scratch that` posts only that command and does not type. Both stays held. The next `all done` posts them once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:22 UTC — a failed please send keeps both prefixes

**Status:** PASS for VA-DELIV-014 at LEVEL 1. Status is up. A transcript POST that fails on `please all done` leaves the prefix as `ship please` and does not type. The next successful `please all done` posts `Ship the notes. ship please send prompt` once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:16 UTC — an up bridge sends both prefixes once

**Status:** PASS for VA-DELIV-013 at LEVEL 1. While `ship` is held and status is already up, `please all done` posts `Ship the notes. ship please send prompt` once and does not type. The next `please all done` posts `please send prompt` only. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:10 UTC — a second prefix stays with the held send

**Status:** PASS for VA-DELIV-012 at LEVEL 1. While `ship` is held, a failed status GET on `please all done` does not type and leaves the prefix as `ship please`. A recovered `all done` posts `Ship the notes. ship please send prompt` once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-14 00:04 UTC — a failed recovered post keeps the prefix

**Status:** PASS for VA-DELIV-011 at LEVEL 1. Status is up. The transcript POST for `all done` returns nothing, so `Ship the notes.` and `ship` stay held and nothing is typed. The next successful POST sends them once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:58 UTC — a recovered status sends the held prefix once

**Status:** PASS for VA-DELIV-010 at LEVEL 1. After a failed `ship all done`, a recovered status and `all done` posts `Ship the notes. ship send prompt` once. The next `all done` posts `send prompt` only. No keystrokes. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:54 UTC — a dead status does not type a held prefix

**Status:** PASS for VA-DELIV-009 at LEVEL 1. While `ship` is held, a failed status GET on `ship all done` does not type `ship` and does not press Enter. A second failure does not copy `ship`. With nothing held, `ship all done` still types. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:48 UTC — a dead status does not press Enter over a held prefix

**Status:** PASS for VA-DELIV-008 at LEVEL 1. While `ship` is held, a failed status GET on `all done` does not press Enter. The sentence and the prefix stay held. `all done` with nothing held still presses Enter. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:42 UTC — a note leaves the send prefix

**Status:** PASS for VA-DELIV-007 at LEVEL 1. After a failed `ship all done`, `Thanks.` posts `Ship the notes. Thanks.` and leaves `ship`. The next `all done` posts `ship send prompt` once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:36 UTC — a retried send posts its prefix once

**Status:** PASS for VA-DELIV-006 at LEVEL 1. After a failed `ship all done`, the next successful `ship all done` posts `Ship the notes. ship send prompt` once. The following success posts `ship send prompt` only. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:30 UTC — a failed send keeps its prefix

**Status:** PASS for VA-DELIV-005 at LEVEL 1. A failed `ship all done` leaves `Ship the notes. ship` and does not type it. A second failure does not copy `ship`. The next successful `all done` posts `Ship the notes. ship send prompt` once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:24 UTC — a failed send post keeps the hold

**Status:** PASS for VA-DELIV-004 at LEVEL 1. After a successful status GET, a transcript POST that returns nothing does not type `all done` and leaves `Ship the notes.` held. The next successful send posts that sentence once. A status GET that fails still keystrokes a send. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:18 UTC — scratch and pause leave the hold

**Status:** PASS for VA-DELIV-003 at LEVEL 1. `scratch that` and `please stop` do not include `Ship the notes.` and do not clear it. The next `all done` still posts that sentence once. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:10 UTC — held sentence rides the next send once

**Status:** PASS for VA-DELIV-002 at LEVEL 1. `Ship the notes.` plus `all done` posts `Ship the notes. send prompt` once on v1 and v2. The next `all done` posts `send prompt` only. Pid 64238 was not restarted. This is not the microphone.

## 2026-11-13 23:02 UTC — dead bridge holds a non-command, still not live

**Status:** PASS for VA-DELIV-001 at LEVEL 1. A status failure no longer types `Ship the notes.` into the focused app. The sentence is held once and is posted once, ahead of the next successful line. Command fallbacks are unchanged. Pid 64238 was not restarted and still types. This is not the microphone.

## 2026-11-13 22:57 UTC — cancel cooldown keeps a wake, still not a recording

**Status:** PASS for VA-HANDY-005 at LEVEL 1. After `cancel that`, the 0.6 s cooldown no longer discards a wake score. Idle speech in that window is still ignored. The dismiss block still refuses the wake. Pid 64238 was not restarted and still drops the score. This is not live dictation.

## 2026-11-13 22:45 UTC — spoken cancel does not submit, still not a recording

**Status:** PASS for VA-HANDY-004 at LEVEL 1. A pause row `cancel that` toggles Handy once, scratches the partial once, and does not post those words. The next wake is one toggle and not a cancel. The history database was not opened. This is not live dictation. Pid 64238 still owns the microphone.

## 2026-11-13 22:35 UTC — cancel clears the partial, recording still stubbed

**Status:** PASS for VA-HANDY-003 at LEVEL 1. Fifteen seconds without speech scratches the partial once, then `handy --cancel` once. The next wake is one `--toggle-transcription` and not another cancel. File mode does not call Handy. The history database was not opened. Pid 64238 was not restarted, so it still skips that scratch. This is not live dictation.

## 2026-11-13 22:25 UTC — one flush, one submit, still not a recording

**Status:** PASS for VA-HANDY-002 at LEVEL 1. A dictation pause calls `handy --toggle-transcription` once and submits `Ship the notes.` once. The history database is not opened. Repeating a partial does not submit. This is not live Handy dictation. Pid 64238 still owns the microphone.

## 2026-11-13 22:15 UTC — Handy flags stubbed, recording still live-only

**Status:** PASS for VA-HANDY-001 at LEVEL 1. Cancel is `--cancel`. Stop and a fresh start are `--toggle-transcription`. A restart cancels first. A stopped app is not launched. File-mode wake does not call Handy. The binary was not executed and `history.db` was not opened. This is not live dictation. Pid 64238 still owns the microphone.

## 2026-11-13 22:05 UTC — playback rate moves the echo reference

**Status:** PASS inside VA-AEC-001. `afplay -r 1.18` for half a second selects 16 kHz samples 8160 through 9439. A 0.25 s pause in that window selects 3440 through 4719, and `cancel_playback_echo` sends that slice. Still not a speaker test. Pid 64238 was not restarted.

## 2026-11-13 21:55 UTC — synthetic echo control, room still unmeasured

**Status:** PASS for VA-AEC-001 at LEVEL 1. `cancel_playback_echo` feeds the WAV cursor through `aec-audio-processing==1.0.0` in 10 ms frames before VAD. A 20 ms speech copy drops at least 20 dB. A second arrival 20 ms later drops at least 12 dB, against 5.0 dB for the 48-tap fit. Unrelated speech keeps more than half its tail energy. The short fit runs only when the import fails. Pid 64238 was not restarted and still owns the microphone, so this is not a room result and not VA-INT-001.

## 2026-11-13 21:45 UTC — canceller chosen, not running

**Status:** DECIDED for VA-AEC-000. The live path still subtracts one 3 ms fit. On white noise, a second arrival 20 ms later left 5.0 dB ERLE, and a 200 ms delay was not touched. The next canceller is `aec-audio-processing==1.0.0` with echo cancellation only, in front of VAD, still using the WAV cursor and `afplay`. The wheel is not installed. Pid 64238 still owns the MacBook microphone, so no speaker-to-mic trial was run. This is not VA-INT-001. See `docs/testing/AEC-DECISION.md`.

## 2026-11-13 21:28 UTC — stop fixture cuts playback

**Status:** PASS for VA-INT-AUTO-041. The stop fixture was rejected before Whisper because the bleed floor absorbed the first loud frames and the hold dropped the onset. Hot frames are no longer added to that floor, and a short clip is transcribed before resume. Real `afplay` 50930 died and did not return. A second turn played. This is not the physical microphone and not VA-INT-001.

## 2026-11-13 21:17 UTC — fixture pipeline, stop not cut

**Status:** PARTIAL for VA-INT-AUTO-040. A second controller was not started. `FixtureAudioSource` fed the same `handle_captured_frame` path. Wake, Handy `--transcribe-file`, and two submits landed on OMP pid 47508 port 49919. Playback started both turns. The stop fixture did not cut `afplay`; the slot ended with `reason: end`. This does not prove acoustic echo cancellation and does not pass VA-INT-001. Pid 16590 and pid 64238 were not signaled. `status.json` was unchanged.

## 2026-11-13 20:58 UTC — still no input for the real pipeline

**Status:** BLOCKED for LEVEL 4 and for VA-INT-001. Rechecked `sounddevice`, AVFoundation, and `system_profiler`. The only input is the MacBook Pro Microphone, default device 0, and controller pid 64238 opens that stream with `sounddevice.InputStream` and no device argument. `/Library/Audio/Plug-Ins/HAL/ParrotAudioPlugin.driver` is present and does not create a device. The wake, dictation, and stop fixtures were not played. Stop, pause, resume, and hold-on semantics are recorded in VA-INT-AUTO-039; that test stubs playback and is not the audio path.

## 2026-11-13 20:53 UTC — Handy phrases match the controller, still not the mic

**Status:** PASS at LEVEL 3 for VA-INT-AUTO-037. The file path heard `Hey Jarvis.`, `Hold on a second.`, and `The sentence ends with stop.` The controller classifies those strings with playback stubbed. LEVEL 4 is still BLOCKED.

## 2026-11-13 20:51 UTC — Handy can transcribe a file, not the live mic

**Status:** PASS at LEVEL 3 for VA-INT-AUTO-036. `handy --transcribe-file` heard `Good morning.` and `Stop.` from the fixtures. It does not open the microphone. LEVEL 4 is still BLOCKED: the only input is the MacBook mic, owned by controller pid 64238.

## 2026-11-13 20:09 UTC — LEVEL 4 has no second input

**Status:** BLOCKED. `sounddevice` and AVFoundation show only the MacBook microphone and speakers. Playing a wake into that mic would reach controller pid 64238. See `docs/testing/scenarios/VA-INT-AUTO-005-audio-path.md`.

## 2026-11-13 20:07 UTC — isolated barge-in

**Status:** PASS at LEVEL 3 for VA-INT-AUTO-004. Posted only to bridge 63609. Pid 16590's registry was not written.

See `docs/testing/scenarios/VA-INT-AUTO-004-interrupt.md`. Spoken VA-INT-001 is still BLOCKED.

## 2026-11-13 20:06 UTC — autonomous two-turn playback

**Status:** PASS at LEVEL 3 for VA-INT-AUTO-003. Pid 16590 was not touched.

See `docs/testing/scenarios/VA-INT-AUTO-003-two-turns.md`. The spoken VA-INT-001 path is still BLOCKED. Do not wait for pid 16590.

## 2026-11-13 19:49 UTC — VA-INT-001 blocked on the spoken steps

**Status:** BLOCKED

VoiceBox is up. GUI pid `20266` replaced pid `29277`. Server pid `20305` listens on `127.0.0.1:17493` with `--port 17493 --parent-pid 20266`. `GET /health` returned 200, `status: healthy`, `model_loaded: true`, `model_size: 1.7B`, `backend_type: mlx`. `GET /profiles` lists `Akshay`, `Akshay hindi`, and `kishu`. One `POST /generate/stream` for profile `Akshay` (`4bde1e0f-bddd-40cf-9ab1-4b34632b51fd`) returned 200, `audio/wav`, 96044 bytes, 24 kHz, mono, 16-bit, 2.00 s, RMS about 3277. `afplay` exited 0. System output volume was 19 and was not changed. No new crash report. This does not prove a person heard the speaker.

OMP pid `16590` is still `agentBusy` with an empty draft on port `62283`. No POST. The spoken VA-INT-001 script has not been dictated.

**Human action that unblocks the next check:** when that OMP session is idle, say the script in `docs/testing/scenarios/VA-INT-001-pipeline.md` into the mic. Do not quit VoiceBox.

## 2026-11-13 19:40 UTC — server was down

**Status:** cleared at 19:49 UTC by a human reopen. Kept so the crash history stays next to the runbook.

**Scenario:** `docs/testing/scenarios/VA-INT-001-pipeline.md`

**Run record:** `.local/voice-agent/runs/VA-INT-001-2026-11-13.json`

VoiceBox.app `0.5.0` pid `29277` is running. `voicebox-server` is not. Nothing listens on `127.0.0.1:17493`. `GET /health` was refused. No profile list, no generation, no playback.

Rechecked 19:45 UTC. Still no `voicebox-server`, and `/health` on 17493 is still refused. OMP pid `16590` is still `agentBusy` with an empty draft. No POST.

Rechecked 19:47 UTC. Same GUI pid `29277` (one frontmost window, no server child). `/health` refused again. OMP pid `16590` still `R+` and `agentBusy`. No process was quit or started.

VoiceBox `v0.5.0` (`tauri/src-tauri/src/main.rs`) listens on `17493` and auto-starts the sidecar once per launch. It does not start it again after a crash. `.keep-running` was rewritten at 10:12:06 EST, two seconds before server pid `29308` launched, and is only an exit sentinel. The human start is to quit VoiceBox and open it again. An agent must not exec the sidecar and must not kill the GUI. See `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md`.

OMP pid `16590` is a live turn, not a stale flag. At 19:46 UTC it was state `R+`, parent zsh `6265`, with a context7 child and a tiny-inference worker. `GET /status` on port `62283` was `agentBusy: true`, `draftLength: 0`. `agentBusy` is `!ctx.isIdle()`. The bridge does not refuse `/transcript` while that is true. Do not POST. Do not cache `62283`. See `docs/testing/OMP-SESSION-READINESS.md`.

Controller pid `64238` is `IDLE`, `last_action` `cancelled`, status time 2026-11-13 19:27:42 UTC. Handy pid `62365` is running. Neither was restarted. No speech was dictated in this check.

**Human action:** done at 19:49 UTC. VoiceBox was opened again. Do not quit it now.

**Not this blocker:** the 5 s VoiceBox hold in the extension. Unit test VA-TTS-004 passed. The live `speech.log` refusals stopped after 19:31:22 UTC. They are a consequence of the closed port, not a reason to relaunch the server.
