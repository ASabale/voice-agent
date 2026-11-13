# Handy / VoiceBox / OMP Ralph voice loop

You are the only runner of the Handy / Hey Jarvis / VoiceBox / OMP voice loop.

Source of truth:
- `/Users/akshay/Development/voice-agent/HANDY-SCENARIO-CHECKPOINT.md`
- `HANDY-RALPH-VOICE-LOOP-PROMPT.md` for this loop protocol
- Live state:
  - `~/.local/bin/omp-voice-controller status`
  - `~/.local/state/omp-voice/controller.log`
  - `~/.local/state/omp-voice/speech.log`
  - `~/.local/state/omp-voice/status.json`
  - `~/.local/state/omp-voice/tts-playing.json`

Do not trust chat memory. Read the checkpoint fresh each iteration.

## Ralph goal

Make the voice loop feel instant and clean:

1. Handy must hear the wake and dictation correctly.
2. Command phrases must behave correctly: send, stop, scratch, clear, cancel, lookalikes.
3. Our own VoiceBox playback must be recognized as VoiceBox, not user speech.
4. Foreign `afplay` audio must not suppress the wake.
5. TTS output must not lag, stutter, loop, repeat, clip, screech, or stay silent.
6. Service down states must be detected and reported, not hidden inside the mic loop.
7. Fix the controller or extension, restart only the voice controller when needed, and retest the same row until it passes or becomes genuinely blocked.

Do not commit. Do not restart the user's OMP session. Do not reopen already-passed A-G/H/I/J rows unless a code change invalidates them.

## Stop condition

At the end of the run:

- If all pending rows are complete and no new user-facing gap exists, write:

```text
IMPROVEMENT LOOP IDLE
```

inside `HANDY-SCENARIO-CHECKPOINT.md`, then create:

```text
/Users/akshay/Development/voice-agent/.ralph-voice-loop-idle
```

- If the loop is genuinely blocked by a missing service that you cannot start, write a `blocked` row, record the exact reason, and create `.ralph-voice-loop-idle` only after saying clearly what Akshay must restart manually.

Do not create the idle marker while work remains.

## One iteration only

Each run does exactly one thing:

1. Read the checkpoint.
2. Pick the first `pending` or `fail` row.
3. If no `pending` or `fail` row exists, add one new gap row for an actual user-facing failure, or declare idle.
4. Run one deterministic test.
5. Fix if needed.
6. Retest the same row in the same run.
7. Write the observed log lines, latency numbers, state after, result, and fix into the checkpoint.

Do not batch several scenarios unless they are the same bug.

## Preflight every run

Before any scenario test, check:

```sh
~/.local/bin/omp-voice-controller status
curl -fsS http://127.0.0.1:17493/health
curl -fsS http://127.0.0.1:17494/status
```

If VoiceBox `/health` is unreachable:

1. Try to start VoiceBox if available, for example:

```sh
open -a VoiceBox
```

2. Wait up to 60 seconds.
3. Poll `/health` again.
4. If still unreachable, write a row in the checkpoint named `VOICEBOX-DOWN` with:
   - exact error,
   - controller pid,
   - status state,
   - latest relevant `speech.log` failure,
   - result `blocked`.

Do not make the controller loop forever on failed health checks. If health is unreachable, the controller should log at most once per 5 seconds and stop attempting model tier changes.

If the OMP bridge `/status` is unreachable:

- do not restart the user's OMP session;
- write `BRIDGE-DOWN` as blocked;
- stop audio tests that require delivery.

## Build the deterministic harness

If `scripts/voice_ralph_check.py` or an equivalent harness does not exist, create one.

The harness must:

1. Start or inspect the controller.
2. Read controller status.
3. Send synthetic audio through the MacBook Pro microphone path using the voice venv:

```text
~/.local/share/omp-voice/venv/bin/python
```

4. Convert int16 samples to float32 and divide by 32768 before `sd.play`.
5. Do not import `soundfile`.
6. Play wake phrases separately from the continuation.
7. For wake rows:
   - If status is `DICTATING`, say only `Send that.` and wait.
   - If status is `IDLE`, play only the wake.
   - Wait until `controller.log` says `entering DICTATING`.
   - Sleep 1.3 seconds.
   - Then play the continuation.
8. Record:
   - wake score,
   - time from wake to `entering DICTATING`,
   - time from first continuation play to transcript,
   - time from transcript to outcome,
   - final state,
   - whether the log line is the expected one.

Do not use `say` as the only playback mechanism when testing our VoiceBox behavior. If using any `afplay` as a bed, make sure it is marked as our VoiceBox only by writing `tts-playing.json` exactly as the extension does.

## Scenario families that must be verified

### 1. Wake pickup

Pass requires:

- `Hey Jarvis`, `OK Jarvis`, `Hello Jarvis`, or `Jarvis` opens Handy when idle.
- A real wake must score at least the 0.50 threshold.
- Room noise below 0.50 must not open Handy.
- Lookalikes such as `H R V S`, `H R V`, `Hey service`, `A harvest`, `Every service`, and ordinary 15-second speech must not wake Handy.
- Never lower the 0.50 wake threshold.

### 2. Commands during dictation

Pass requires:

- `Send that.` sends.
- Lone `Submit.` sends.
- `said that` inside a sentence does not send.
- `Stop.` pauses and preserves the draft.
- `Hold on a second.` or `Hold on a sec.` during our own TTS stops playback and does not open dictation.
- `Scratch that.` removes the last chunk and stays `DICTATING` for replacement.
- `Clear draft.` clears the draft and stays `DICTATING` for replacement.
- `Cancel that.` cancels the current unpasted chunk and returns to `IDLE`.
- A wake word inside a dictated sentence must not start a second dictation.

### 3. Our VoiceBox barge-in

Pass requires:

- During our own VoiceBox playback, the wake is ignored.
- During our own VoiceBox playback, `Stop.` stops the speech.
- During our own VoiceBox playback, `Hold on a second.` stops the speech.
- During our own VoiceBox playback, `Send that.` does not open dictation.
- During our own VoiceBox playback, `Scratch that.` does not open dictation.
- A sentence ending in `stop` must not stop playback.
- Do not restore a 0.35 TTS open.

### 4. Foreign `afplay`

Pass requires:

- Any `afplay` that does not have `tts-playing.json` marked as ours must not make the assistant deaf.
- A wake during a foreign bed must open Handy and send the checkpoint if the row expects it.
- If a foreign bed causes `Ignored ... over TTS`, that is a fail.

### 5. Partial transcript behavior

Pass requires:

- Partials are written to the focused field before the final Handy flush.
- The final partial includes the last word before the pause.
- The final sent draft is one draft, not the partial plus the final chunk duplicated.
- The partial is removed before final send.

### 6. TTS latency

Measure and write into the checkpoint:

- time from assistant reply to first VoiceBox request in `speech.log`;
- time from VoiceBox request to `tts-playing.json` `playing: true`;
- time from playback start to playback end;
- number of failed TTS requests with `ECONNREFUSED`;
- number of `VoiceBox health unread` lines per minute.

Fail if:

- VoiceBox is reachable but replies are silent;
- short replies take more than 5 seconds to begin speaking without a clear model-load reason;
- the controller logs health failures every mic frame;
- repeated failed health checks make the controller sluggish.

Fix latency issues with one-variable probes:

1. Is VoiceBox actually listening on 17493?
2. Is the OMP bridge listening on 17494?
3. Is the controller stuck in the strata/model-tier loop?
4. Is sentence generation blocking playback?
5. Is `afplay` being killed too late or too early?
6. Is barge-in pausing playback because speaker bleed is treated as stop speech?

### 7. TTS audio quality

Create or update a small harness that generates a known sentence through VoiceBox and stores the WAV.

The WAV must:

- exist;
- be nonempty;
- have sane duration for the sentence;
- not clip;
- not contain repeated fragments;
- not produce screech or raw int16 scale errors;
- have no unexplained long silent gaps.

Then verify what the mic hears by either:

- playing the WAV and letting Handy/Whisper transcribe it in a controlled test, or
- recording the mic during playback and comparing the transcript to the intended sentence.

Fail if the heard text contains stutter, loops, missing tail words, repeated phrases, or a screech.

## Fix protocol for a failed row

For each failure:

1. Reproduce it deterministically.
2. Minimize the repro to the smallest scenario that still fails.
3. State 3-5 falsifiable hypotheses.
4. Add targeted instrumentation, not log-everything noise.
5. Fix the controller or extension.
6. Restart only the voice controller if needed:

```sh
~/.local/bin/omp-voice-controller stop
~/.local/bin/omp-voice-controller start
```

7. Retest the exact same row.
8. Mark `pass` only when the checkpoint `expect` column matches the observed log.

If the fix is only a workaround, say so. Prefer root-cause fixes:

- service availability checks;
- bounded retry/backoff;
- one source of truth for "is VoiceBox speaking";
- clear command parsing rules;
- no repeated health polling every mic frame;
- no duplicated TTS sentence;
- no partial final-send double writes.

## Checkpoint write format

When you finish a row, update the row in the checkpoint with:

```text
result: pass | fail | blocked
heard: <timestamp, controller log line, status state, latency numbers>
fix: <what changed, or why no fix was needed>
next: <next user-facing gap, or none>
```

If a row says "Do not rerun", do not rerun it unless a new fix changes the behavior.

## Exit

If every open row is closed, write `IMPROVEMENT LOOP IDLE`, create `.ralph-voice-loop-idle`, and stop. Do not invent extra rows to keep the loop alive.
