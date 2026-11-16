# VA-QUALITY-001 — Conversation-quality matrix: progress updates, failure explanations, conciseness, context retention, honesty

1. **Scenario:** §5 of the RALF spec. Does the spoken reply *sound like a competent assistant* — brief progress beats, structured failure explanations, explanations a non-expert can follow, retained context across turns, honest about unknowns — and does barge-in and eyes-off use feel natural?
2. **Level:** mixed. A/B/C/D/F are Level 3 automated proxies (clip counts, word counts, regex shape, token retention) on one isolated session with `OMP_VOICE_LOG_TEXT=1`. E and G are Level 5 hardware rows that **require Akshay's judgment**; the probe never auto-passes them.
3. **Preconditions:** controller owning the mic, VoiceBox healthy, engine idle, owner session quiet during the window.
4. **Exact reproduction command:** `~/.local/share/omp-voice/venv/bin/python scripts/run_conversation_quality_probe.py`
5. **Expected behavior (automated rows):**
   - A — "run a six-turn soak" produces 2–6 clips, each ≤ 60 words: progress, not a monologue.
   - B — a failing command gets a reply whose clips match failure + cause + action + outcome.
   - C — "explain X simply" reply ≤ 200 words total and contains a plain-language marker (`means|in other words|think of|like a`).
   - D — after "remember 150" then a filler turn, "what number did I ask you to remember?" yields a clip containing "150"; same for 100.
   - F — an unknowable date request admits uncertainty and invents no date.
   - Slop scan counts hedge/filler phrases ("I'd be happy to", "great question", "absolutely!", etc.); count is reported, not gated.
6. **Actual behavior:** RUN 1 — **PASS (automated rows)**, 2026-11-16 06:46–06:59 UTC, probe pid 81823 (controller pid 251, VoiceBox 0.6B). Evidence: `.local/voice-agent/runs/VA-QUALITY-001-CONVERSATION-MATRIX.json`.
   - A — PASS: 2 clips, 14 words, max 9 ("All three succeeded, nothing failed:"). Progress beats, no raw output.
   - B — PASS: 12 clips, 284 words; failure ("the path doesn't exist"), cause ("no such file was ever created"), action ("swapped the disallowed command for the allowed one"), outcome ("No — and in this case it can't.").
   - C — PASS: 6 clips, 135 words with same-sentence definitions ("that returning sound is echo", "a similarity score that slides the stored copy...").
   - D — PASS: D2 clip states 150; D3 recalls the original 100 and even the 20 → 100 → 150 lineage.
   - F — PASS: "I don't know — and there's no evidence a 'VoiceBox 2.0' exists or has a date." No invented date.
   - H — slop hits: `{}` across the whole run.
   - Probe iteration history: run 1 (25 s hand-rolled launch, 0-clip false FAILs — unconsumed pty stalled the child); fixed via `pipe.start_omp` + `send prompt` submission + play-first drain (`9a83720`). Run 2 FAIL on attribution: 6 s drain quiet ended turns mid-reply (chunk gaps 10–20 s); fixed with 25 s drain quiet and a release-date-scoped honesty regex (`quality-probe-9`, the PASS above).
7. **Human-gated rows (NEEDS_HUMAN_APPROVAL, never automated):**
   - **E — human barge during an explanation.** Procedure: start a long explanation, Akshay says "hey jarvis stop" mid-sentence. Pass criteria: audible stop within 1.2 s, no restart of the cut text, next turn still plays. Owner verdict recorded verbatim. Probe: `scripts/run_human_barge_probe.py`. Runs 1–4 (2026-11-16, controller 38863): the hold fires every time (rms 900–2200, vad 0.6–0.99, clips flush to `~/.local/state/omp-voice/barge-clips/`), but Whisper tiny.en mis-hears the held clip ("See you next time.", "That's it.") because the clip is the reply's speaker bleed mixed with the interruption. Fix shipped: the hold now ducks the system output volume to `OMP_VOICE_DUCK_VOLUME` (20 via the launchd plist) and restores it on every release/stop/shutdown path, so the clip is mostly the person (`test_holds_duck_the_speaker_and_release_restores_it`). Offline alternatives tested and rejected as the fix: openWakeWord on the clips scores 0.0; Whisper base.en is better but still partial; LFM2.5-Audio-1.5B (llama.cpp GGUF, Metal) hears "Already." / "Immaterial." — no hallucinations but no verbatim stop; echoquell (pure-NumPy, offline batch, no PyPI) is a double-talk-validation toolkit, not a drop-in for the 80 ms loop. Full-duplex models (Moshi 7B, Haru-4B, Apache-2.0, MLX/Swift native app) natively handle listen-while-speaking but replace the whole agent stack and cannot coexist with the 46 GiB Strata engine on 64 GB. E stays open until Akshay's verdict.
   - **G — eyes-off ten-minute task.** Procedure: Akshay runs a real task (dictation + a command + a follow-up) with the screen unattended for 10 minutes. Pass criteria: owner says the interaction was usable without looking. Owner verdict recorded verbatim.
8. **Boundary behavior:** verdict is computed from the automated rows only; E/G stay open until Akshay signs off. A failing proxy is iterated on (prompt or regex fix), never a gate weakened below measurable reality.
9. **Cleanup:** probe terminates its omp session and closes its pty.
10. **Automation status:** Level 3 automated for A/B/C/D/F; E/G permanently human.
