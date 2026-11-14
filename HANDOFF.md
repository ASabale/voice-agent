# HANDOFF — voice agent

This file is a pointer, not a status. The single authoritative engineering status is the "Current engineering status" section at the top of `HANDY-SCENARIO-CHECKPOINT.md`, cross-checked against the level-tagged catalogue in `docs/testing/INDEX.md`. Historical rows and retrospectives below those sections are dated evidence; they are never live state. Do not write a second status summary here or anywhere else.

## Where each question is answered

| Question | Read |
|---|---|
| What is the current engineering status, by validation level? | `HANDY-SCENARIO-CHECKPOINT.md`, top section |
| Which fixes are tested but not yet running live? | `HANDY-SCENARIO-CHECKPOINT.md`, "Tested but not loaded into running processes" |
| Which test belongs to which level (1 unit, 2 fixture, 3 local service, 4 physical acoustic, 5 extended reliability)? | `docs/testing/INDEX.md` and `HANDY-RALPH-VOICE-LOOP-PROMPT.md` |
| How to recover VoiceBox without spawning duplicates? | `docs/testing/VOICEBOX-SERVICE-RUNBOOK.md` |
| Is an OMP session safe to send a prompt to? | `docs/testing/OMP-SESSION-READINESS.md` |
| Why WebRTC and not a loopback device or VoiceProcessingIO? | `docs/testing/AEC-DECISION.md` |
| What are the operating rules for one loop iteration? | `HANDY-RALPH-VOICE-LOOP-PROMPT.md` |

## How to derive live state (never cache it)

There is no fixed OMP bridge port. Each session binds port 0 and writes `~/.local/state/omp-voice/sessions/<pid>.json`; the controller resolves the port from that registry (`omp_bridge.url` in `omp-voice-controller status`). Port 17494 is legacy and is used only when `lsof` shows a listener whose pid is the chosen session. Re-derive every pid and port at the start of every run:

```sh
~/.local/bin/omp-voice-controller status
curl -fsS -m 2 http://127.0.0.1:17493/health
ls ~/.local/state/omp-voice/sessions/
```

Snapshot verified 2026-11-14 03:43 UTC, valid only until the next run: controller pid 64238 `IDLE`; bridge ok for pid 82521 on ephemeral port 61707; VoiceBox healthy on 17493 with the 0.6B model loaded. Ports like 17494, 56876, 57042, 59036, 62283, and 63609 are historical observations of different sessions; none of them is an assumption.

## Open gate

The only remaining validation level with no passing row is Level 4 (physical acoustic): VA-INT-001 and the five AEC acceptance criteria. It is blocked because controller pid 64238 holds exclusive ownership of the MacBook Pro Microphone; a second mic does not exist (VA-INT-AUTO-005, VA-INT-AUTO-038). Everything below Level 4 has deterministic fixtures.
