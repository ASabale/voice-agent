# VA-INT-AUTO-001 — Isolated print session

1. **ID:** VA-INT-AUTO-001
2. **Name:** Isolated OMP print session
3. **Objective:** A second OMP process answers a fixed prompt without touching the user's busy session.
4. **Level:** LEVEL 3 for the text reply. Not LEVEL 4. Not VA-INT-001.
5. **Command:** From the repo root. `omp-voice-controller start` returns immediately when pid 64238 is already running, so this does not restart it.

```sh
mkdir -p .local/voice-agent/omp-test-sessions .local/voice-agent/runs
omp -p \
  --no-tools --no-skills --no-rules --no-context-files \
  --session-dir .local/voice-agent/omp-test-sessions \
  -e "$PWD/extension/voicebox-speech.ts" \
  --max-time 3m \
  --cwd "$PWD" \
  "Respond with exactly: Voice integration test successful."
```

6. **Do not:** POST to pid 16590, kill it, or start a second VoiceBox. Port 17493 already has a server.
7. **Observed 2026-11-13 20:00:58 UTC:** Pid 23924 wrote `sessions/23924.json` with port 63281, then exited. Stdout was `Voice integration test successful.` The session file `2026-11-13T20-00-57-996Z_01a1d67f-bc8c-727e-8e2c-db82cbf728d5.jsonl` has that user message and that assistant message. Pid 16590 stayed on port 62283 with `agentBusy: true`. Its registry file was not rewritten.
8. **Speech:** `speech.log` at 20:01:00Z requested 34 characters and then `AbortError`. Print mode exited before playback. The 130-character generate at 20:00:03Z is wav `omp-vb-16590-4.wav`, which belongs to pid 16590, not this test.
9. **Not done:** No status GET while 23924 was alive. No wake, no Handy transcript, no second turn.
10. **Next:** Keep the process alive until the 34-character generate finishes. Do not send this prompt again only to reprint the same sentence.
