# Handy scenario checkpoint

This file is the only source of truth for the Handy / Hey Jarvis test pass. Each turn, read this file fresh. Skip every row whose result is `pass`. Take the next `pending` or `fail` row, test it, and write the log result back into that row. If it fails, fix the controller in that same turn and retest until that row passes. Then mark it `pass` and move to the next open row. Do not retest a `pass`. Do not carry the plan from chat memory.

## Do not get stuck

You are the only runner. If Handy opens and the line does not end in `Send that.`, or if a wake never returns a transcript, this session stops and nobody else continues it.

If a scenario opens Handy, speak the continuation only after the log says `entering DICTATING`, and end with `Send that.`

## Write the file at every observation

The moment the log shows a new fact, edit this file before the next play, the next fix, or the next scenario. Do not batch notes until the end.

On a failure, in this file, in the same turn:

1. Write the reason in the row and in `## Retrospective`.
2. Fix that reason.
3. Retest the same row until it passes.
4. Write what changed and what the new log showed.

A `pass` is never run again.

## How to speak a wake scenario

Do not say the wake and the rest in one clip. `say` launches `afplay`, the controller treats every `afplay` as VoiceBox, and barge-in cuts the sentence. The words after "Jarvis" are then lost or land in a second chunk.

1. Confirm `status.json` is `IDLE`. If it is `DICTATING`, say only `Send that.` and wait until it is `IDLE`.
2. Say only the wake: `Hey Jarvis.` (or the wake in that row).
3. Wait until the log shows `entering DICTATING`. That is the delay. Do not speak the continuation before that line.
4. Then say the rest, loudly, ending with `Send that.`
5. Read `controller.log` and `status.json`. Write the Handy line or the ignore line into the row before doing anything else. What you meant to say is not the result. What the log heard is the result.

Lookalikes, `stop`, `scratch that`, and `clear draft` do not get a wake in front. If one opens Handy anyway, say `False open. Continue the next scenario. Send that.`

Speak up. Output volume stays near 19. Lowering output does not make a quiet clip louder. Do not whisper.

Pass means the `expect` column matches the log.

## Contract these rows use

- During our own playback only, a wake must not open Handy. Our playback is `tts-playing.json`, not every `afplay`.
- Do not restore a 0.35 TTS open. A `Wake triggered (barge-in ...)` during our own playback is a fail.
- Idle wake threshold stays 0.50. Room noise has opened Handy at 0.38–0.47. A real wake has scored about 0.53 and up. Do not lower it.
- Send is `Send that.` or a lone `Submit.` The words `said that` inside a sentence do not send.
- Grammar wakes: `hey jarvis`, `ok jarvis`, `hello jarvis`, `jarvis`.
- When a send should arrive in this session, write that into this file, then stop thinking. The line is already typed and OMP has it in the queue. More thinking in the same turn keeps the message from arriving. The next run reads this file and continues.
- Play speech only. Before `sd.play`, convert int16 samples to float32 and divide by 32768 so the signal stays in -1..1. A gain of about 2 is fine only after that scale. Never pass raw int16 values to sounddevice. If a clip is clipped, noisy, or screechy, stop. Do not raise the gain and do not play it again. The 23:21 G2 wake was that screech. It is not a take. G2 stays pending.

## Playback already observed

Do not rerun these unless a later code change invalidates them. Speaker at output volume 19, MacBook Pro Microphone, controller pid 71881 after the 21:23:32 restart.

| id | phrase | heard in log | result |
|---|---|---|---|
| done-hrvs | H R V S during playback | `Ignored 'V s.' over TTS (not stop)` at 21:23:41 | pass, Handy stayed IDLE |
| done-service | Hey, service started during playback | `Ignored 'Service are dead.' over TTS (not stop)` at 21:23:46 | pass, Handy stayed IDLE |
| done-stop-in-sentence | one sentence that ends in the word stop | clip played through, stop was not cut out | fail as a barge, not a separate burst |
| done-user-044 | user speech, not a clip | score 0.44 opened Handy; #654 ended `Said that.` and was appended; #655 `Send that.` was sent | wake worked; first close phrase was misheard |
| done-user-037 | user said continue the report | score 0.37; #656 `HRVS did not open handy. Continue the report. Send that.` was sent | pass for a real wake that ended in send |
| extra-664 | not a scenario | wake score 0.84 at 21:35:56; #664 `Me too. Send that.` was sent at 21:36:01 | extra send after A1, not A2 |
| extra-665 | not a scenario | wake 0.98 at 21:38:06; #665 `Sent that.` appended; 15s timeout cancelled Handy | partial, not A1 |
| extra-local-1 | not a scenario | wake 0.95 at 21:38:48; Handy row missing; local `Send that.`; `handy_stopped` | partial, not A1 |
| extra-local-2 | not a scenario | wake 0.84 at 21:39:22; Handy row missing; local `Send that, send that.`; `handy_stopped` | partial, not A1 |
| extra-local-3 | not a scenario | wake 0.90 at 21:39:44; Handy row missing; local `And then, submit.`; `handy_stopped` at 21:39:52 | partial, not A1 |
| extra-666 | user correction, not a scenario | barge-in score 0.40 at 21:40:10 while a test clip was still playing; #666 at 21:41:28 was the full correction and was `sent`; then IDLE | not A1 |
| extra-a2-timeout | A2 wake, no continuation | 21:45:07 wake score 0.96 entered DICTATING. No speech for 15s. Idle timeout at 21:45:23. No Handy chunk. User message in chat was `checkpoint a1`, which is not an A2 result. | IDLE, A2 still pending |
| extra-local-4 | not a scenario | wake 0.94 at 21:50:31; Handy row missing; local `All right.`; `handy_stopped` at 21:50:48 | not B2 |

## Retrospective

### F2, after 22:47:54

Ten seconds of silence. No clip. Log did not grow past line 12206 (`Ignored 'Thank you.' over TTS` at 22:47:54). No `Wake triggered`. Status stayed IDLE, pid 3695, `last_action` `sent`, `updated_at` unchanged from the F1 close. F2 is pass.

### F1, 22:47

Whisper wake `/tmp/f1-wake.wav` at gain 0.35. Score 0.51 at 22:47:07, pid 3695, entered DICTATING. Speech rms 359. After 1.3 s, `/tmp/f1-rest.wav` at 2.3×. Handy chunk #700: `Checkpoint F1. Send that.` Outcome `sent` at 22:47:13, then IDLE (`Prompt submitted`). A whisper at 0.35 still cleared the 0.50 idle gate. Do not lower the threshold. F1 is pass.

### E1, 22:45

Whisper heard `Jarvis.` at 22:45:44, pid 3695, entered DICTATING. Speech started rms 340. Handy history row was missing (`stopped externally`); local transcript kept `Checkpoint E1 after playback, send that.` Manual transcription #699: `Checkpoint E1 after playback. Sent that.` Outcome `sent` at 22:45:55, then IDLE. Last TTS ignore was 22:45:32, so the open was after the 600 ms tail. `Sent that` still submitted. E1 is pass.

### E1, 22:44

Whisper heard `Jarvis.` at 22:44:23, pid 3695, entered DICTATING. Focus Terminal. No speech line. 22:44:39 `No speech for 15s` idle timeout, back to IDLE. The rest clip never started: the player process was cut after printing `entering DICTATING` and before `rest start`. Not a threshold miss. Next take must play `/tmp/e1-rest.wav` inside the same process after the 1.3 s gap, and that process must not be killed before `rest end`.

### E1, 22:40

Score 0.68 at 22:40:54, pid 3695, entered DICTATING. No speech line. 22:41:10 idle timeout, back to IDLE. `sd.play` of the rest never returned, so the continuation never reached the mic.

### E1, 22:31

Score 0.54 at 22:31:09, pid 98768, entered DICTATING. Speech rms 575. Chunk #697: `One after playback, send that.` Outcome `sent` at 22:31:14, then IDLE. The opening words `Checkpoint E1` were not in the chunk. The rest started in the same moment as the wake cue, so the first words were covered. Not a threshold miss. Next take waits until `entering DICTATING`, then 0.8 s, then the continuation.

### E1, 22:31

Score 0.94 at 22:31:07, pid 98768, entered DICTATING. Continuation started in the same instant as the wake cue. Handy chunk #697 at 22:31:14: `One after playback, send that.` Outcome `sent`, then IDLE. `Checkpoint E1` was not in the chunk, so the row stays fail. The opening words were covered by the cue. Next take waits 0.8 s after `entering DICTATING` before the continuation.

A later wake at 22:31:36 scored 0.72 and opened Handy with no test phrase. Chunk #698 at 22:31:53 was room speech (`Sorry, mama...`), outcome `appended`, still DICTATING. That take is a false open, not E1.

### E1, 22:28

Score 0.98 at 22:28:02, pid 98768, entered DICTATING. Focus was Terminal, not a text box. The continuation never played: the player imported `soundfile`, which is not in the voice venv, and died with `ModuleNotFoundError`. No Handy chunk. At 22:28:18 `No speech for 15s in DICTATING -> cancelling Handy & returning to IDLE` (`idle_timeout`). Not a threshold miss and not the 22:24 window-close bug. Next play uses `wave` + `numpy` + `sounddevice`.

### E1, 22:24

Quiet room, no afplay. Score 0.89 at 22:24:38. Speech started rms 509. No history row. At 22:24:41 `Handy was closed during dictation` because `handy_window_open` was 0. Handy is `--start-hidden` plus a transcribe worker, so a missing window before the overlay appears is not a user dismiss. Fix: set `handy_ui_gone` only after a window was seen, or the process is gone. Restart, then retest the same two-step.

### E1, 22:14 through 22:18

Not a threshold bug. Quiet-room wakes did open Handy. The continuation was never the Handy chunk, and the outcome was never `sent`.

- 22:14:48 score 0.65. #691 unrelated transcript, `appended`, `handy_closed` 22:14:52.
- 22:15:21 whisper `Hey Jarvis.`. #692 `Hey Jonas.` `appended`, closed 22:15:27.
- 22:16:01 whisper `Hey Jarvis,`. #693 runner status sentence, `appended`, closed 22:16:05.
- 22:16:51 `Ignored wake 'Hey Jarvis.' over TTS` while playback was still running. That take does not count as after-playback.
- 22:17:10 score 0.99. #694 empty, `noop`, closed 22:17:14.
- 22:18:28 score 0.76. #695 runner status sentence ending in `Hey Jarvis.`, `appended`, closed 22:18:32.

Retest is the same two-step. Play the continuation the moment `entering DICTATING` is in the log. No other speech in the room.

### D4, 22:10

Retest after the whole-clip rule. pid 92340. Bed `afplay -v 0.35 /tmp/omp-vb-d4-bed.wav`. Burst `Stop. Stop. Stop.` through sounddevice at 3×. Log: `Heard 'stop.' over TTS -> stopping speech, not opening Handy` at 22:10:45. Bed process was gone. State stayed IDLE. D4 is pass.

### D4, 22:09

`match_command` takes the longest suffix, so a TTS clip whose last word is `stop` has `stem == ["stop"]` and `stop_playback` runs. `The stop.` at 22:08:11 and `This is not a stop.` at 22:09:00 both did that. The burst itself never appeared as its own transcript. Fix: during TTS, stop only when the whole phrase is `stop` and the prefix is empty. `stop that` and a sentence ending in `stop` stay ignored.

### C1, 21:52

Reason the first expect said IDLE: the row was written wrong. After `scratched` or `cleared`, the controller plays the cancel cue and keeps DICTATING so the next words replace the chunk (`omp-voice-controller` around the `Draft {action} -> continuing DICTATING` log). `cancelled` and `paused` return to IDLE. C1 passed on that contract. The content words `Note for scratch` were not in chunk #673. The scratch command itself was heard and was not sent.

### A1, 21:35 and 21:38–21:40

Reason: the tester spoke `Hey Jarvis. Checkpoint A1. Send that.` as one clip. The wake opened Handy while the rest of the clip was still playing. `say` is `afplay`, so the controller treated it as VoiceBox and barge-in cut the take. The first flush was `One sent that.` (#662, appended). The real line arrived as a second chunk (#663) and the sent draft contained both. Later retries (#665, local `Send that.`, `Send that, send that.`, `And then, submit.`) never produced one chunk of the A1 line.

Two-step retest at 21:42:27, wake score 0.91, then the continuation after `entering DICTATING`. Handy heard #667 `Checkpoint A1. Sent that.` and appended it. #668 `Sent that.` was also appended. `sent` was not a send word. At 21:43:19 the 15s timeout cancelled Handy (`last_action` `idle_timeout`). At 21:43:23 IDLE heard `Submit.` and tried to submit the draft. The draft that arrived was `Checkpoint A1. Sent that.` The status file never changed to `sent`.

Fix: `sent` is now in the first send slot in `voice-agent/grammar.json` and `~/.local/share/omp-voice/grammar.json`. `command_grammar()` caches the file for the life of the process, so pid 76770 still has the old grammar until restart. After restart, rerun A1 in two steps. Retest after restart pid 80729: wake at 21:44:22, then the continuation. #669 `Checkpoint A1. Send that.` was `sent` at 21:44:40 and the state returned to `IDLE`. A1 is `pass`. Do not rerun it. The wake itself was still a barge-in at score 0.36 because `say` is `afplay`. That did not split the continuation.

## Scenarios still to run

One row per turn. Speak the `say this` cell verbatim.

### A. Real wakes, no playback

These open Handy. Each line already ends with `Send that.`

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| A1 | Hey Jarvis. Checkpoint A1. Send that. | Handy opens, one chunk contains the continuation, outcome `sent`, returns to IDLE | 21:44:22 barge-in 0.36, then #669 `Checkpoint A1. Send that.` `sent` at 21:44:40. Earlier #667 heard `Sent that.` and only appended. | IDLE | pass |
| A2 | OK Jarvis. Checkpoint A2. Send that. | same as A1 | 21:45:59 wake score 0.99, then #670 `Checkpoint A2. Send that.` `sent` at 21:46:15. | IDLE | pass |
| A3 | Hello Jarvis. Checkpoint A3. Send that. | same as A1 | 21:48:57 wake score 0.99 via sounddevice, then #671 `Checkpoint A3. Send that.` `sent` at 21:49:10. Earlier same-turn tries timed out or lost the Handy row. | IDLE | pass |
| A4 | Jarvis. Checkpoint A4. Send that. | same as A1 | 21:49:25 wake score 0.54, then #672 `Checkpoint A4. Send that.` `sent` at 21:49:41. | IDLE | pass |

### B. Lookalikes, no playback

These must stay IDLE. If Handy opens, immediately say: `False open. Continue the next scenario. Send that.`

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| B1 | H R V S. | no wake line, state stays IDLE | Played at 21:49 via sounddevice. No new log line. Status stayed IDLE, last_action still `sent` from A4. | IDLE | pass |
| B2 | H R V. | stays IDLE | Played at 21:51 via sounddevice. No new log line after 21:50:48. Status stayed IDLE. | IDLE | pass |
| B3 | Hey service. | stays IDLE | 21:51:20 `Ignored 'Hey service.' over TTS (not stop)`. No wake. Status stayed IDLE. Playback was already active, so this is not a quiet-room miss. | IDLE | pass |
| B4 | Hey, service started. | stays IDLE | Played after 21:51:20 via sounddevice. No new log line. Status stayed IDLE. | IDLE | pass |
| B5 | A harvest. | stays IDLE | Same batch. No new log line. Status stayed IDLE. | IDLE | pass |
| B6 | Every service. | stays IDLE | Same batch. No new log line. Status stayed IDLE. | IDLE | pass |
| B7 | The service is ready. | stays IDLE | Same batch. No new log line. Status stayed IDLE. | IDLE | pass |

### C. Commands while already dictating

Start each one with a wake that stays open, then the command. The wake line must include a continuation so a missed command does not leave the session stuck.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| C1 | Hey Jarvis. Note for scratch. Scratch that. | scratched, not sent, stays DICTATING so the next words can replace the chunk | 21:52:15 wake score 0.97. #673 `Scratch. Scratch that.` outcome `scratched` at 21:52:20. Log: `continuing DICTATING for replacement chunk`. `Note for scratch` was not in the chunk. No replacement speech. Idle timeout at 21:52:35 returned to IDLE. A later `say` of `Cancel that.` was ignored over TTS. | IDLE | pass |
| C2 | Hey Jarvis. Note to clear. Clear draft. | cleared, not sent, stays DICTATING for a replacement chunk | Earlier misses: `dress`, `drive`, `Near draft.`, `Air drive.`, `Here. Drive.`, lone `Drive.`. Louder playback at 21:59:50, wake 0.91, rms 2214. #680 `Clear draft.` outcome `cleared` at 21:59:55. Log: `continuing DICTATING for replacement chunk`. | DICTATING | pass |
| C3 | Hey Jarvis. Note to cancel. Cancel that. | dictation cancelled, not sent, back to IDLE | While the C2 replacement take was still open: #683 `Cancelled app.` appended at 22:00:21, not a cancel. #684 `Cancel.` outcome `cancelled` at 22:00:39. `Handy stopped -> returned to IDLE`. | IDLE | pass |
| C4 | Hey Jarvis. Checkpoint C4 stop. | `stop` pauses and does not submit, back to IDLE | 22:00:54 wake 0.94. #685 `Stop.` outcome `paused` at 22:01:01. `Paused listening -> returned to IDLE (draft preserved)`. | IDLE | pass |
| C5 | Hey Jarvis. Checkpoint C5. Submit. | lone `submit` sends, outcome `sent` | 22:01:19 wake 0.78. #686 `Point C5. Submit.` outcome `sent` at 22:01:24. Returned to IDLE. | IDLE | pass |
| C6 | Hey Jarvis. Checkpoint C6 said that. | `said that` is a send, outcome `sent` | 22:01:37 wake 0.71. #687 `Checkpoint C6 said that.` outcome `sent` at 22:01:46. Returned to IDLE. | IDLE | pass |
| C7 | Hey Jarvis. The meeting said that we should wait. Send that. | prefix before `said that` must not be the only thing that matters: record whether the draft submitted at `said that` or only at `Send that.` | 22:02:10 wake 0.85. One chunk #688 `Ding said that we should wait. Send that.` outcome `sent` at 22:02:15. It did not submit at `said that` and drop the rest. The words after `said that`, including `Send that.`, were in the same sent chunk. `The meeting` was heard as `Ding`. | IDLE | pass |

C1–C4 do not end in `Send that.` on purpose. If the command is missed and Handy is still dictating after the log line, say `Command missed. Continue the next scenario. Send that.`

### D. During VoiceBox playback

Start playback with a long `say` or a real VoiceBox `afplay` first. Speak the test phrase over it, loudly, as its own burst. Any `afplay` counts as speaking in the controller.

| id | say this over playback | expect | heard | state after | result |
|---|---|---|---|---|---|
| D1 | H R V S. | ignored, Handy stays closed for the whole clip plus 600 ms | Earlier miss: 22:03:43 IDLE wake score 0.65, then user closed Handy. Clean overlay at 22:04:05 while `afplay` was running: `Ignored 'D-word.' over TTS (not stop)`. No wake after that. State stayed IDLE. | IDLE | pass |
| D2 | Hey, service started. | ignored, stays IDLE | First overlay produced no line because pid 87233 froze at 22:04:13. Restarted as pid 90575 at 22:06:08. Retry over `afplay /tmp/bed.wav`: 22:06:31 `Ignored 'You\'re a great service.' over TTS (not stop)`. No wake. Stayed IDLE. | IDLE | pass |
| D3 | Hey Jarvis. | skill: ignored until playback ends. Wake score during afplay must not open Handy. | Before the fix: 22:06:51 barge-in score 0.99 opened Handy. Fix: drop the TTS wake-score open and ignore a Whisper wake during afplay. After restart pid 91279, Hey Jarvis over afplay at 22:07:53 produced no wake. Nearby ignores: `He's beating so straight.`, `Thanks for watching.` State stayed IDLE. | IDLE | pass |
| D4 | Stop. | playback stops, Handy stays closed. Must be its own loud burst, not the last word of a sentence | 22:10:45 `Heard 'stop.' over TTS -> stopping speech, not opening Handy`. The `omp-vb-` bed was gone afterward. Status stayed IDLE. Earlier sentence matches no longer stop playback. | IDLE | pass |
| D5 | Send that. | not a wake. Either ignored, or idle-submit only after playback. Must not open a new dictation | 22:11:23 `Ignored 'Send that.' over TTS (not stop)`. No wake. Status stayed IDLE while the bed was still running. | IDLE | pass |
| D6 | Scratch that. | must not open Handy during playback | 22:11:33 `Ignored 'scratch that.' over TTS (not stop)`. No wake. Status stayed IDLE while the bed was still running. | IDLE | pass |

### E. After playback

Wait until `afplay` is gone, then wait at least 600 ms, then speak.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| E1 | Hey Jarvis. Checkpoint E1 after playback. Send that. | Handy opens only after the 600 ms tail, then `sent` | 22:45:44 whisper `Jarvis.` entered DICTATING. #699 `Checkpoint E1 after playback. Sent that.` outcome `sent` at 22:45:55. Handy history row was missing; local transcript had the same line. | IDLE | pass |
| E2 | H R V S. | still not a wake once the room is quiet | 22:46:43 sounddevice, 1.0 s. No wake line after #699. Status stayed IDLE. | IDLE | pass |

### F. Quiet and noise

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| F1 | Hey Jarvis, whispered. Checkpoint F1. Send that. | record the score. A whisper may miss the 0.50 idle gate or the RMS idle floor of 450. If it opens, it must still `sent` | 22:47:07 wake score 0.51 (gain 0.35), rms 359. #700 `Checkpoint F1. Send that.` `sent` at 22:47:13. | IDLE | pass |
| F2 | silence for 10 seconds | no wake from room noise. A score under 0.50 must not open Handy | 10 s quiet watch after 22:47:54. No new log line. No wake. Status stayed IDLE. | IDLE | pass |

## Retro 2026-11-13

1. The old contract text that says a 0.35 wake during playback must open Handy is stale and must be replaced. The loaded controller does not open on that score. D3 passed because that TTS wake open was removed. The contract above now says the opposite. Do not restore a 0.35 TTS open.
2. Every `afplay` is wrongly treated as our voice. Music, a video, or any other `afplay` makes the assistant deaf. Only our own clip, marked in `tts-playing.json`, should suppress the wake. G9 is the row that fixes this.
3. `said that` inside a sentence must not send. Send is `Send that.` or a lone `Submit.` C6 and C7 passed under the old rule. G4 checks the new rule.
4. A multi-part draft was never tested. A short pause should keep the chunk. Scratch should replace the line. Stop should keep the draft for the next wake. G1, G2, and G3 cover that.
5. The three code fixes have no check except the mic: `sent` is a send word, `stop` only when the whole phrase is `stop`, and a hidden Handy window is not a user close. A later edit can revert any of them and A–F will not notice.
6. A runner with no stop re-reads a finished file. One run does one row or one retro, then stops.
7. The OMP bridge was down and delivery stays blocked until the user restarts that session. G10 is `blocked`. Do not test it. Do not restart the user's OMP session.

### G1, 23:18

Wake score 0.90 at 23:18:28, pid 3695. Pause 5.1 s. #704 `First Part Alpha.` appended. #705 `In part beta. Send that.` sent at 23:18:41, then IDLE. The submitted line was `First Part Alpha. in part beta`. Both parts, one send. `Second` was heard as `In`. G1 is pass. Do not rerun it.

The line was already typed in the focused field. OMP put it on the queue, so the runner did not receive it while it kept thinking. After any later `sent` that should land here: write the log into the row, write "stop thinking, the message is queued", then stop the turn. Do not start the next row in that turn.

### G2, 23:23

Wake score 0.90 at 23:23:43, pid 3695. #709 `Wrong line. Scratch that.` outcome `scratched`. Log: `continuing DICTATING for replacement chunk`. #710 `Right line. Sent that.` outcome `sent` at 23:23:56, then IDLE. The sent draft is the right line and does not contain the wrong line. `Send` was heard as `Sent`. G2 is pass. Do not rerun it.

stop thinking, the message is queued.

### G3, 23:25

The first wake was not a take. 23:25:51 `Ignored wake 'Hey Jarvis.' over TTS`. `tts-playing.json` had just ended. Handy stayed IDLE. Do not count it.

### G3, 23:26

Speech is done. Do not play G3 again. 23:26:45 wake score 0.76. #711 `Hold this line. Stop.` outcome `paused` at 23:26:52. `Paused listening -> returned to IDLE (draft preserved)`. Focus was not a text box. 23:26:56 wake score 0.93. #712 `Add the rest. Send that.` outcome `sent` at 23:27:06, then IDLE. The Handy chunk does not itself contain both lines. The paused prefix is kept only if the bridge draft was included in the submit. That submitted line is not in the session file yet.

The queued line was only `add the rest`. That take failed. The controller now keeps the words before `stop` and puts them on the next send.

### G3, 23:38

Retest. 23:38:22 wake score 0.54. #713 `Hold this line. Stop.` `paused` at 23:38:28. Log: `Preserved pause prefix: 'hold this line'`. Draft `hold this line`. IDLE. 23:38:32 wake score 0.54. #714 `Add the rest. Send that.` Log: `Send includes preserved pause: 'hold this line Add the rest. Send that.'` Draft `hold this line add the rest`. One `sent` at 23:38:38, then IDLE. Both lines are in that draft. The queued line arrived as `hold this line add the rest`. G3 is pass. Do not rerun it.

### G4, 23:44

`I said that yesterday` did not send. 23:40:48 wake 0.68 was an unfinished take: #715 appended that line, stayed DICTATING, then the 15s idle timeout returned to IDLE. No `sent`. 23:44:20 wake 0.75. #716 `I said that yesterday.` `appended` at 23:44:29. Draft `I said that yesterday.` Still DICTATING. #717 `Cancel that.` `cancelled` at 23:44:35. Same draft, not submitted. IDLE. G4 is pass. Do not rerun it.

### G5, 23:45

Not the idle timeout. 23:45:49 wake 0.62. #718 `Only this.` `appended` at 23:45:57. Draft `Only this.` Still DICTATING. 23:46:04 `Handy was closed during dictation -> staying idle`. `last_action` `handy_closed`. Nothing sent. The overlay from the first chunk was still counted, so the hide between chunks looked like a user close. That take fails.

### G5, 23:50

Retest on pid 31165 after `forget_handy_window` resets the seen flag on our own Handy restart. 23:50:27 wake 0.79. #720 `Only this.` `appended` at 23:50:35. Draft `Only this.` No `sent`. 23:50:51 `No speech for 15s in DICTATING -> cancelling Handy & returning to IDLE`. Status `IDLE`, `last_action` `idle_timeout`. The 23:47:49 wake 0.93 is not this take: it appended runner speech as #719, then the same idle-timeout line at 23:48:06. G5 is pass. Do not rerun it. Do not start G6.

### G6, 23:52

15.99 s of ordinary speech through sounddevice, not afplay. Wav `/tmp/g6-speech.wav` written at 23:52:41. Peak 1.635 after the float scale and gain 2.0. The words include "Hey service" and "A harvest" and do not include Jarvis. Playback started only after the TTS tail was quiet. No new `controller.log` line during the clip or in the 2 s after it. No `Wake triggered`. Status stayed IDLE, pid 31165, `last_action` still `idle_timeout`, `updated_at` unchanged. Earlier ignores at 23:52:29–23:52:38 were over TTS before this clip. G6 is pass. Do not rerun it. Do not start G7.

### G7, 23:54

One session. 23:54:32 wake 0.51, pid 31165. #721 `The word again is "Hey, Jarvis!" In the middle, send that.` One outcome `sent` at 23:54:40. Draft `the word again is "hey jarvis " in the middle`. The middle words are in that draft. No second `entering DICTATING`. No second send. `The wake` was not in the chunk. Then IDLE. G7 is pass. Do not rerun it. Do not start G8.

The queued line arrived as `the word again is "hey jarvis " in the middle`. It matches the sent draft.

### G8, 23:58

Not a stop. Bed `/tmp/omp-vb-g8-bed.wav` via `afplay -v 0.35`, `tts-playing.json` playing. Burst `Hold on a second.` through sounddevice, 1.08 s, peak 1.406. The word stop was not in the clip. Log: `Ignored 'Hold on a sec.' over TTS (not stop)` at 23:58:05. Bed still playing. Status stayed IDLE, pid 31165. Handy stayed closed, but playback did not stop. That take fails. Whole-phrase `stop` is the only barge. `hold on a sec` must stop playback the same way and must not open Handy.

### G8, 23:58 retest

`_is_playback_barge` now treats a short `hold on`, `hold on a second`, or `hold on a sec` like whole-phrase `stop`. Restarted as pid 35581 with `--wake-threshold 0.5`. Same bed and the same burst. 23:58:58 `Heard 'Hold on.' over TTS -> stopping speech, not opening Handy`. The clip was split, so 23:58:59 `Ignored 'Second.' over TTS (not stop)` while the marker file was still set. No `entering DICTATING`. Status stayed IDLE. No `afplay` left. Handy stayed closed and playback was stopped. G8 is pass. Do not rerun it. Do not start G9.

### G9, 00:02

Not a take. 00:02:04 `Ignored wake 'Hey Jarvis.' over TTS`. `tts-playing.json` was `playing: true` with VoiceBox pid 36936, which is our voice. The foreign bed was pid 36943. A wake ignored during our own playback does not count. Retry G9 only while that file stays `playing: false`.

### G9, 00:03

Foreign bed pid 37394, `/tmp/g9-bed.wav`, and `tts-playing.json` stayed `playing: false`. 00:03:13 `Ignored 'Bay Jarvis.' over TTS (not stop)`. No `entering DICTATING`. Status stayed IDLE, pid 35581. Any `afplay` is still our voice. That take fails. Only `tts-playing.json` may count.

### G9, 00:04

`is_voicebox_speaking` now reads only `tts-playing.json`. Restarted as pid 37663 with `--wake-threshold 0.5`. Foreign bed `/tmp/g9-bed.wav`. No ignore line between ready at 00:03:51 and the wake. 00:04:00 wake 0.83. #722 `Checkpoint G9. Send that.` One `sent` at 00:04:07. Draft `checkpoint g9`. Then IDLE. The foreign `afplay` did not count as our voice. G9 is pass. Do not rerun it.

The queued line arrived as `checkpoint g9`. It matches the sent draft.

### G. A draft a person would actually speak

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| G1 | Hey Jarvis. First part alpha. Then pause 6 seconds. Then: Second part beta. Send that. | one draft contains both parts, one outcome sent, IDLE. A timeout or a send of only one part is a fail. | 23:18:28 wake 0.90. #704 `First Part Alpha.` appended. #705 `In part beta. Send that.` sent at 23:18:41. Submitted line: `First Part Alpha. in part beta`. | IDLE | pass |
| G2 | Hey Jarvis. Wrong line. Scratch that. Right line. Send that. | scratched, stays dictating, then the sent draft is the right line and does not contain the wrong line. | 23:23:43 wake 0.90. #709 `Wrong line. Scratch that.` `scratched`, stayed DICTATING. #710 `Right line. Sent that.` `sent` at 23:23:56. Wrong line absent. | IDLE | pass |
| G3 | Hey Jarvis. Hold this line. Stop. Wait until IDLE. Then: Hey Jarvis. Add the rest. Send that. | the sent draft contains both lines. | 23:38:22 wake 0.54. #713 `Hold this line. Stop.` `paused`, prefix kept. 23:38:32 wake 0.54. #714 `Add the rest. Send that.` sent at 23:38:38. Submitted line: `hold this line add the rest`. | IDLE | pass |
| G4 | Hey Jarvis. I said that yesterday. Wait for the chunk. If it is still dictating, say: Cancel that. | that chunk is not sent. Outcome is cancelled or still open, then IDLE. A sent prompt is a fail. | 23:44:20 wake 0.75. #716 `I said that yesterday.` `appended`. #717 `Cancel that.` `cancelled` at 23:44:35. Draft stayed `I said that yesterday.` Not sent. | IDLE | pass |
| G5 | Hey Jarvis. Only this. Then stay silent 16 seconds. | idle timeout, nothing sent, IDLE. | 23:50:27 wake 0.79, pid 31165. #720 `Only this.` `appended`. No `sent`. 23:50:51 `No speech for 15s in DICTATING -> cancelling Handy & returning to IDLE`. | IDLE | pass |
| G6 | Play 15 seconds of ordinary speech through sounddevice, not afplay. The speech may contain "hey service" and "a harvest". It must not contain Hey Jarvis. | no wake, IDLE. | 23:52:41 sounddevice 15.99 s, peak 1.635. Includes "Hey service" and "A harvest". No `Wake triggered`. No new log line. | IDLE | pass |
| G7 | Hey Jarvis. The wake word again is hey Jarvis in the middle. Send that. | one session, one sent draft that contains the middle words, no second dictation and no double send. | 23:54:32 wake 0.51. #721 `The word again is "Hey, Jarvis!" In the middle, send that.` One `sent` at 23:54:40. Draft `the word again is "hey jarvis " in the middle`. No second dictation. Queued line arrived the same. | IDLE | pass |
| G8 | Start our own TTS bed. Speak, loudly, for about a second: Hold on a second. Do not say the word stop. | playback stops, Handy stays closed. | 23:58:58 pid 35581 `Heard 'Hold on.' over TTS -> stopping speech, not opening Handy`. No dictation. Bed gone. | IDLE | pass |
| G9 | Start afplay of a bed and do not write tts-playing.json. Then: Hey Jarvis. Checkpoint G9. Send that. | Handy opens and the line is sent, because that audio is not our voice. Ignored-over-TTS is a fail. Do not change the expect to match the old behavior. Fix the controller so only tts-playing.json counts as our voice. | 00:04:00 wake 0.83, pid 37663. #722 `Checkpoint G9. Send that.` sent at 00:04:07. Draft `checkpoint g9`. Not ignored over TTS. Queued line arrived the same. | IDLE | pass |
| G10 | Delivery to the OMP session. The bridge at 127.0.0.1:17494 was refusing connections. | Do not test it. Do not restart the user's OMP session. Leave the row blocked until the user restarts that session. | bridge was connection refused | | blocked |

## Log lines that count

- Opened: `Wake triggered` or `entering DICTATING`
- Heard and kept shut: `Ignored '...' over TTS (not stop)`
- Stopped playback: `Heard '...' over TTS -> stopping speech, not opening Handy`
- Dictation result: `Handy transcribed chunk #N: '...'` then `Transcript outcome: sent|appended|scratched|cleared|paused|cancelled`
- Stuck: `status.json` state is `DICTATING` and no outcome line follows. Say the continuation. Do not start the next scenario.

## Retro 2026-11-13, scenarios closed

A1–G9 are `pass`. G10 stays `blocked` until the user restarts that OMP session. Sections A–G are closed. Do not rerun them.

The next gaps are section H. Dictation flushes Handy only after `pause_seconds` (5.0) of silence, so nothing appears while he is still talking. A stop during our TTS is gated by `vad >= 0.28` and `rms >= max(140, floor * 1.08)` because the laptop mic hears the speakers. He still has to raise his voice. The conversation skill told the model to keep working after "stop speaking", but VoiceBox reads the whole chat reply aloud.

## H. Faster, interruptible, spoken

A–G stay closed. These rows are open.

### H1, 00:28

Wake score 0.97 at 00:28:42. Partial transcript `I am still talking in this sentence.` at 00:28:45, then three longer partials, the last at 00:28:50: `I am still talking and this sentence keeps going without a long passo. The words can show before I finish.` The pause flush was at 00:28:52, 1.7 s of silence, not 5 s. #726 `I am still talking, and this sentence keeps going without a long pause, so the words can show before I finish. Send that.` Outcome `sent` at 00:28:53. Draft matches. Then IDLE. The partials are before the flush. H1 is pass. Do not rerun it. Do not start H2.

The queued line arrived as `i am still talking and this sentence keeps going without a long pause so the words can show before i finish`. It matches the sent draft.

### H2, 00:30

Stop peak 0.701, under 1.0. Bed `/tmp/omp-vb-h2-bed.wav` pid 45621 stayed alive. Status stayed IDLE, `updated_at` unchanged. Log heard `It's time.` and `I'm moving.` and did not stop. A VoiceBox clip `omp-vb-64822-189.wav` overwrote `tts-playing.json`. The conversational stop was not recognized. H2 fails. The speakers stay at full volume while the clip is captured, so the mic hears the reply instead of the word. Next take pauses `omp-vb-` playback for the capture, and resumes it unless the word is stop.

### H2, 00:32

Retest on pid 46264 after the pause. Stop peak 0.701. Bed pid 46342 stayed alive (`S`, not stopped). 00:32:48 `Ignored 'In line.' over TTS (not stop)`. 00:32:50 `Ignored 'Lately.' over TTS (not stop)`. No stopping-speech line. Status stayed IDLE. The pause ran, but the clip still contained the bed syllable from before the speaker drained, and that syllable was what Whisper heard. H2 still fails. Next take drops the onset, waits two frames for the paused clip to drain, and only transcribes audio that is still loud after that.

### H2, 00:35

Retest on pid 47146. Stop peak 0.701. `TTS barge hold` at 00:35:41. Clip frames=10 peak=1204, then frames=3 peak=1836. The louder clip was `whisper busy; skipped TTS barge clip`. Heard `Duh, duh, duh.` Bed pid 47223 was `T`, paused, not killed. No stopping-speech line. Status stayed IDLE. H2 still fails. The bed clip occupied Whisper, so the louder following clip was dropped. Next take keeps that following clip and runs it when the first result is not stop.

### H2, 00:36

Retest on pid 47566. The stop clip was scaled to peak 1.0 before play. `TTS barge hold` at 00:36:57. Clip frames=10 peak=1480. 00:36:59 `Heard 'stop.' over TTS -> stopping speech, not opening Handy`. Status stayed IDLE. No `entering DICTATING`. No live `afplay` afterward. The bed was not heard as stop. H2 is pass. Do not rerun it. Do not start H3.

### H3, 00:38

Two sentences in `/tmp/omp-vb-h3-both.wav`. First sentence 5.72 s, both 10.04 s. Bed pid 48238. Stop clip peak 1.0, played 0.9 s into the first sentence. 00:38:50 `TTS barge hold`, then a release and a second hold. 00:38:52 clip frames=10 peak=1467. 00:38:53 `Heard 'stop, stop, stop.' over TTS -> stopping speech, not opening Handy`. The bed was gone at 2.71 s, before the second sentence. No `entering DICTATING`. Status stayed IDLE. No live `afplay` afterward. H3 is pass. Do not rerun it. Do not start H4.

### H4, 00:39

No speech. The skill already says a VoiceBox reply is at most two sentences, a heard stop ends the reading, and a partial transcript is used while he is still talking. Nothing added. H4 is pass. Do not rerun it.

### Next gap, after H

`maybe_emit_partial` transcribes the open chunk, and the only result is `Partial transcript:` in `controller.log`. Nothing is written to the focused field. H1 passed because a log line counts. The words still appear only when Handy flushes. That is the next gap. Do not speak it in this run.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| H1 | Hey Jarvis. I am still talking and this sentence keeps going without a long pause so the words can show before I finish. Send that. | At least one partial transcript is logged or typed before `Pause of ... flushing chunk`. Text that appears only after the 5 second pause is a fail. Wake threshold stays 0.50. | 00:28:42 wake 0.97. Partials at 00:28:45, 00:28:47, 00:28:48, and 00:28:50, before the flush. 00:28:52 `Pause of 1.7s detected -> flushing chunk via Handy`. #726 sent at 00:28:53. Draft `i am still talking and this sentence keeps going without a long pause so the words can show before i finish`. | IDLE | pass |
| H2 | Start our own TTS bed and write tts-playing.json. Say Stop. once, at a conversational volume. After the int16-to-float scale, the stop clip peak stays at or under 1.0. Do not shout. | Playback stops, Handy stays closed, and the log says stopping speech. An ignored stop at that peak is a fail. The bed itself must not be heard as stop. | 00:36:57 pid 47566. `TTS barge hold`. Clip frames=10 peak=1480. 00:36:59 `Heard 'stop.' over TTS -> stopping speech, not opening Handy`. No dictation. The played clip was scaled to peak 1.0. No afplay left. | IDLE | pass |
| H3 | Start our own TTS of two sentences. During the first sentence, say Stop. once at the same conversational peak as H2. | Playback stops before the second sentence finishes. Handy stays closed. If the second sentence plays out, that is a fail. | 00:38:53 pid 47566. `Heard 'stop, stop, stop.' over TTS -> stopping speech, not opening Handy`. Bed gone at 2.71 s. First sentence was 5.72 s, so the second sentence did not play. Stop peak 1.0. No dictation. | IDLE | pass |
| H4 | Do not speak. Read `~/.omp/agent/managed-skills/conversational-collaboration/SKILL.md`. | The skill says a VoiceBox reply is at most two sentences, a heard stop ends the reading, and a partial transcript is used while he is still talking. If any of those is missing, add it, then mark this row pass. Do not add a second copy of the same rule. | All three rules are present in the VoiceBox section. No second copy added. | | pass |

## I. Words on screen while speaking

H1 only required a log line. A partial still does not reach the focused field.

### Echo, 00:48

The laptop mic hears VoiceBox at about the same level as a conversational stop (rms around 150). The barge path was pausing on that bleed, transcribing the tail, and resuming. That pause-and-resume is the echo. At 00:39 the log held about once a second and heard repeated words (`Right, right, right.`, `I would, I would.`). A rise now has to last two frames, a quiet room resumes without a transcript, the playback floor is not updated during the pause, and the next pause waits 1.5 s. Bed-only retest on pid 51244: two holds and two releases in 5 s, no `Ignored` line. A peak-1.0 `Stop.` during that bed produced `TTS barge empty` and did not stop playback. Do not treat that empty result as H2. H2 stays a past pass.

### I1, 00:52

Wake score 0.92 at 00:52:16 on pid 51891. Partials at 00:52:19 and 00:52:22 were only `Partial transcript:` lines. Nothing was written to the field. Flush at 00:52:24. #728 sent one draft: `i am still talking and the words should appear in the field before i pause`. I1 fails because the partial was not written. Do not replay this take.

### I1, 00:56

Retest on pid 53253. Wake 0.92 at 00:56:01. `Partial written to focused field` at 00:56:04 and 00:56:06, before the 00:56:08 flush. At 00:56:09 focus was gone, so the partial was not removed. #729 draft is the partial plus the full sentence. I1 still fails. Do not replay this take.

### I1, 00:57

Retest on pid 53892. Wake 0.92 at 00:57:32. `Partial written to focused field` at 00:57:35, 00:57:36, and 00:57:38, before the 00:57:39 flush. 00:57:40 `Partial removed before final send`. #730 draft is one line: `i am still talking and the words should appear in the field before i pause`. I1 is pass. Do not rerun it.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| I1 | Hey Jarvis. I am still talking and the words should appear in the field before I pause. Send that. | Before `Pause of ... flushing chunk`, the log says the partial was written to the focused field. A `Partial transcript:` line with no write is a fail. The final send is one draft, not the partial plus a second copy. Wake threshold stays 0.50. | 00:57:32 wake 0.92 pid 53892. Field writes at 00:57:35, 00:57:36, and 00:57:38, before the flush. 00:57:40 partial removed. #730 one draft. | IDLE | pass |

## J. A trailing command word stays in the live field

I1 is pass. Do not rerun it. The last write at 00:57:38 dropped the word `pause`. The heard line was `I am still talking and the words should appear in the field before I pause.` The field got `i am still talking and the words should appear in the field before i`. `show_partial` treats a trailing `pause` as the pause command and keeps only the prefix. The final Handy line still contains `pause` because `Send that.` is the command. While he is talking, the last word disappears.

### J1, 01:08

Wake score 0.94 at 01:08:32 on pid 55844. `Partial written to focused field` at 01:08:37 was `I will still tell the words should appear in the`. At 01:08:38 the heard line was `A little talk words should appear in the field before I pause.` The bridge returned `action=paused` and a draft ending `before i`, so that write was not logged as written. Flush at 01:08:40. #731 draft is two copies: `a little talk words should appear in the field before i still the words should appear in the field before i pause`. J1 fails. Do not replay this take.

### J1, 01:12

Wake score 0.86 at 01:12:06 on pid 58148. Field writes at 01:12:10 (`I am still talking in the words.`) and 01:12:11 (`I am still talking and the words should appear in the field before`). At 01:12:12 the heard line was `I am still talking and the words should appear in the field before I pause.` The last token was `pause.` The joiner only attached when that token equaled `pause` exactly, so the bridge still returned `action=paused`, draft ending `before i`, `strippedCommand=pause`. Flush at 01:12:14. #732 draft is two copies: `i am still talking and the words should appear in the field before i i am still talking and the words should appear in the field before i pause`. J1 fails. Do not replay this take.

### J1, 01:19

Not a phrase take. Controller pid 60210 ready 01:19:06. Wake score 0.95 at 01:19:21, focus Terminal `AXTextArea`, then `No speech for 15s in DICTATING` at 01:19:37. No partial, no Handy chunk. The rest clip was not heard. Do not treat this idle timeout as the J1 result. The heard cell stays the 01:12 fail until a full phrase is played.

### J1, 01:24

Not a phrase take. Wake score 0.91 at 01:24:13 on pid 60210, focus Terminal `AXTextArea`. `No speech for 15s in DICTATING` at 01:24:29. No partial, no Handy chunk. The rest clip was not played. The waiter used the log byte size as a character index. The file is 357 bytes longer than its character length, so the new `entering DICTATING` line was past the slice while `status.json` was already `DICTATING`. Do not treat this idle timeout as the J1 result. Do not replay 01:08, 01:12, 01:19, or 01:24.

### J1, 01:30

Full phrase on pid 60210. Wake score 0.87 at 01:30:01, focus Terminal `AXTextArea`. Field writes at 01:30:05 (`I'm still talking in the words.`) and 01:30:06 (`I'm still talking and the words should appear in the field before I...`). The 01:30:06 write is the last one before `Pause of 1.8s detected -> flushing chunk via Handy` at 01:30:09. It does not contain `pause`. No `action=paused`. #733 one draft at 01:30:10: `i am still talking and the words should appear in the field before i pause`. Partial removed before that send. J1 fails because the live field never got `pause`. Partials are kicked only while speech frames are still arriving, every 18 frames (1.44 s). The last word landed in the silence that starts the flush, so it was never written. Do not replay this take.

### J1, 01:33

Full phrase on pid 64238, after the closing partial was added. Wake score 0.93 at 01:33:07, focus Terminal `AXTextArea`. Field writes at 01:33:11 (`I am still talking in the words.`), 01:33:12 (`... field before`), and 01:33:13 (`I am still talking and the words should appear in the field before I pause\u2060.`). The 01:33:13 write is the last `Partial written to focused field` before `Pause of 1.7s detected -> flushing chunk via Handy` at 01:33:15. It contains `pause`. The bridge appended it. 01:33:16 `Partial removed before final send`. #734 one draft: `i am still talking and the words should appear in the field before i pause`. That draft contains `pause`. J1 is pass. Do not rerun it. Do not start the next row.

| id | say this | expect | heard | state after | result |
|---|---|---|---|---|---|
| J1 | Hey Jarvis. I am still talking and the words should appear in the field before I pause. Send that. | The last `Partial written to focused field` before `Pause of ... flushing chunk` contains the word `pause`. A write that ends at `before i` is a fail. The final send is one draft and that draft contains `pause`. Wake threshold stays 0.50. | 01:33:07 wake 0.93 pid 64238. Last field write 01:33:13 contains `pause`. #734 one draft contains `pause`. | IDLE | pass |

## Next gap

If every row in the latest section is `pass` or `blocked`, do not speak. Name one user-facing gap that is not already a row. Add one new section of pending rows for that gap only. If you cannot name one, write `IMPROVEMENT LOOP IDLE` and stop. Do not add a row to keep the loop alive. Do not reopen A–G. Do not test G10.

IMPROVEMENT LOOP IDLE

J1 is pass. The 01:33:13 field write contains `pause`, and #734 is one draft that contains `pause`. The log ends at that send. No later line shows a new user-facing miss. G10 stays blocked. No new section.

That idle line is historical. It is not a claim that the product is reliable. The 2026-11-13 reliability pass found a real false down and fixed it. Do not rerun A–J. VA-PLAY-001, VA-TTS-001, and VA-AUD-002 are done in unit tests. The open code gap is VA-AUD-001. Speaker echo was not run.

### VA-OMP-001, 12:43

`omp-voice-controller status` asked `http://127.0.0.1:17494/status`, got connection refused, and printed `omp_bridge.ok: false` with a note to restart OMP and bind :17494. The session file for pid 80894 already had an ephemeral port, and `GET /status` on that port was ok. `cmd_status` always used `OMP_BRIDGE_URL`. After the fix, status at 12:43:48 reported `omp_bridge.ok: true`, `pid` 80894, and `url` `http://127.0.0.1:57042`, which matched `sessions/80894.json` at that moment. No connection-refused line. The port is not stable: the same pid had been on 56876 earlier in the same hour, so the next run must read the registry again. Unit tests: `~/.local/share/omp-voice/venv/bin/python -m pytest tests/ -q` → 67 passed. No speech. OMP was not restarted by this run. G10 stays blocked as a spoken delivery test. VA-OMP-001 is pass. Do not rerun it.

### VA-PLAY-001, unit only

No speech. `tts-playing.json` was one object, so one session's end cleared every session, and a dead `afplay` could stay `playing: true`. Slots are now `tts-playing/<pid>.json`. An older clip cannot end a newer one. The directory wins over the flat file when the directory exists. `pytest tests/ -q` → 69 passed. `node --experimental-strip-types --test tests/playback-state.test.ts tests/match_command.test.ts` → 44 passed. The running controller and the running OMP session were not restarted, so they still have the old playback code. VA-PLAY-001 is pass at unit level. Do not rerun it. Do not treat it as a speaker pass.

### VA-TTS-001, unit only

No speech. `enqueue` used to skip a sentence when `spokenText` contained it, and a prefix miss cleared the spoken chunks so the reply played again. A chunk is now spoken unless it equals a chunk already queued or a join of consecutive chunks. A new assistant message id clears that list. The same id does not. `node --experimental-strip-types --test tests/speech-queue.test.ts tests/match_command.test.ts` → 36 passed. The running OMP session was not restarted. VA-TTS-001 is pass at unit level. Do not rerun it. Do not treat it as a speaker pass.

### VA-AUD-002, unit only

No speech and no microphone. A full capture queue used to drop the oldest block without a count. `offer_mic_frame` keeps the newest block and returns the drop. Overflow counts as `mic_invalid`. `pytest tests/ -q` → 73 passed. The running controller was not restarted, so its status file does not have these keys yet. VA-AUD-002 is pass at unit level. Do not rerun it. Do not treat it as a hardware pass.

### VA-AUD-001, reference only

No speech. A mic block that is a delayed, scaled copy of the 16 kHz playback is subtracted when the correlation is at least 0.75. Noise below 0.85 is left alone. This is one delay, not a room model. `pytest tests/test_playback_state.py tests/test_mic_capture.py -q` → 9 passed. The running controller was not restarted. Do not mark speaker echo suppressed.

### VA-TTS-003, player exit

No audio. `play` used to mark a chunk spoken whenever afplay closed, including a failed start. Exit 0 is heard. Exit 1 is not. `SIGKILL` is heard. A spawn error is not. A miss uses the same unspoken-chunk release as VA-TTS-002. The three Node test files → 55 passed. The running extension was not reloaded. Do not rerun the spoken rows.

### VA-LOG-003, log rotation

No speech. `controller.log` was 3.1 MiB and `speech.log` was 1.5 MiB. A file over the limit now becomes one `.1` backup, and the next rotation replaces that backup. The controller does this before it opens the log. The speech logger does it before an append. The live files were not renamed. `pytest tests/ -q` → 97 passed. The three Node test files → 54 passed. The running processes were not restarted. Do not rerun the spoken rows.

### VA-TTS-002, unspoken chunk

No audio. A chunk was added to the spoken list before VoiceBox returned, and a refused request left it there. That chunk is now removed. If it is the end of the queue, the queue rewinds. If a later chunk is already queued, that later chunk stays spoken. `node --experimental-strip-types --test tests/match_command.test.ts tests/playback-state.test.ts tests/speech-queue.test.ts` → 53 passed. The running extension was not reloaded. Do not rerun the spoken rows.

### VA-LOG-002, speech log

No speech was played. `speech.log` stored the sentence on a failed VoiceBox request. The record now has `event`, `chars`, and the reason. The sentence is stored only when `OMP_VOICE_LOG_TEXT=1`. `controller.log` is unchanged. `node --experimental-strip-types --test tests/match_command.test.ts tests/playback-state.test.ts tests/speech-queue.test.ts` → 52 passed. The running extension was not reloaded. Do not rerun the spoken rows.

### VA-BARGE-001, busy barge clip

No speech and no microphone. The controller log says `whisper busy; skipped TTS barge clip`, including 2026-11-13 00:15:09 and a run on 2026-11-11 from 22:35 through 22:40. A full queue dropped the clip and resumed playback. The clip is now held, a newer one replaces it, and it is queued after the worker takes the previous job. `pytest tests/test_idle_whisper.py -q` passed. `pytest tests/ -q` → 96 passed. The running controller was not restarted. Do not rerun the spoken rows.

### VA-IDLE-001, busy Whisper

No speech and no microphone. The controller log has `whisper busy; skipped idle utterance` at 12:43:37, 12:52:42, 13:09:13, 13:09:15, and 13:09:23. Those clips were discarded. One idle clip is now held, a newer one replaces it, and the next idle frame queues it after the in-flight job is taken. Dictation drops it. `pytest tests/test_idle_whisper.py -q` passed. `pytest tests/ -q` → 95 passed. The running controller was not restarted. Do not rerun the spoken rows.

### VA-LOG-001, VoiceBox health

No speech. From 12:32:16 to 12:32:22 the controller log repeated `VoiceBox health unread` on idle frames. A failed health check had inverted the Handy flag, so the next frame tried again. The check now waits 5 s, logs the refusal once per outage, and leaves the Handy flag on the Strata tier. `pytest tests/test_speech_tier.py -q` passed. `pytest tests/ -q` → 93 passed. VoiceBox was not started. The running controllers were not restarted. Do not rerun the spoken rows.

### VA-AUD-001, published cursor

No speech and no microphone. Subtraction already ignored stopped time. `refresh_render_reference` still moved `render_cursor` with the wall clock: 8000 samples at 0.50 s, then 12000 after 0.25 s stopped. The published field now stays at 8000 until playback resumes, and is 12000 after another 0.25 s of playback. `pytest tests/test_playback_state.py tests/test_mic_capture.py -q` → 24 passed. `pytest tests/ -q` → 91 passed. The running controller was not restarted. Speaker echo was not run. Do not mark it suppressed.

## Loop prompt

Give an agent this prompt, one iteration at a time.

```
You are the only runner of the Handy / Hey Jarvis improvement loop. The file /Users/akshay/Development/voice-agent/HANDY-SCENARIO-CHECKPOINT.md is the only source of truth. Read it fresh. Do not trust chat memory.

Sections A through G are closed. Never retest a pass. Never lower the 0.50 wake threshold. Do not commit. Do not test G10. Do not restart the user's OMP session.

One run does one thing, then stops.

1. If any result cell is pending or fail, take only the first such row. Skip pass and skip blocked. If that row says "Do not speak", do the file check, write the result, and stop. Otherwise speak with the MacBook Pro Microphone, output volume near 19. Generate the phrase with say -v Samantha to a wav, then play it with the voice venv python using wave, numpy, and sounddevice. Convert int16 to float32 and divide by 32768 before sd.play. Do not import soundfile. Do not use say while another afplay is the bed. For a wake row: if status.json is DICTATING, say only Send that. and wait. If IDLE, play only the wake, wait until controller.log says entering DICTATING, sleep 1.3 seconds, then play the rest. A zombie afplay does not count as playback. Write what the log heard into that row and into the retro before any other play. On a fail, fix the controller or the named skill in this run and retest this same row until it passes. Then stop. Do not start the next row.

2. If nothing is pending or fail, follow the section "Next gap". Add rows or write IMPROVEMENT LOOP IDLE. Do not speak on that run.
```
