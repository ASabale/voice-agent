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
6. **Actual behavior:** NOT_RUN — probe committed (`833d1fa988`), executed after the clean soak PASS. Evidence will land in `.local/voice-agent/runs/VA-QUALITY-001-CONVERSATION-MATRIX.json`.
7. **Human-gated rows (NEEDS_HUMAN_APPROVAL, never automated):**
   - **E — human barge during an explanation.** Procedure: start a long explanation, Akshay says "hey jarvis stop" mid-sentence. Pass criteria: audible stop within 1.2 s, no restart of the cut text, next turn still plays. Owner verdict recorded verbatim.
   - **G — eyes-off ten-minute task.** Procedure: Akshay runs a real task (dictation + a command + a follow-up) with the screen unattended for 10 minutes. Pass criteria: owner says the interaction was usable without looking. Owner verdict recorded verbatim.
8. **Boundary behavior:** verdict is computed from the automated rows only; E/G stay open until Akshay signs off. A failing proxy is iterated on (prompt or regex fix), never a gate weakened below measurable reality.
9. **Cleanup:** probe terminates its omp session and closes its pty.
10. **Automation status:** Level 3 automated for A/B/C/D/F; E/G permanently human.
