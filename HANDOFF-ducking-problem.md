# Handoff: barge ducking is too eager and does not reliably recover

Repo: `/Users/akshay/Development/voice-agent` (branch `main`, HEAD `aa73e36`). Controller: `bin/omp-voice-controller` (~4630 lines), symlinked at `~/.local/bin/omp-voice-controller`, run by launchd as `com.akshay.omp-voice-controller`. Live pid was **59356**; `launchctl kickstart -k gui/$(id -u)/com.akshay.omp-voice-controller` reloads it (owner authorized). Trace: `~/.local/state/omp-voice/barge-trace.jsonl` (stages: `hold`, `duck`, `duck_restore`, `clip`, `whisper`, `resume`, `stop_playback`, `speaking`), clip dumps in `~/.local/state/omp-voice/barge-clips/` (`OMP_VOICE_BARGE_TRACE=1`, already in the plist).

## Symptom (owner-reported, 2026-11-16)
1. **Any slight environmental sound ducks the speaker volume** while VoiceBox is speaking — cough, keyboard, distant talk — and the duck flickers the whole reply.
2. **Volume sometimes never comes back up** after a duck.
3. In the human barge test (E row of `docs/testing/scenarios/VA-QUALITY-001-conversation-matrix.md`): owner said "hey jarvis stop"; volume went *low right after he finished speaking*, then came back; speech never stopped; repeated "stop" attempts failed; eventually the wake word fired instead.

## Mechanism (where the code is)
- While TTS is active, every 80 ms mic frame is scored in `handle_captured_frame` (`bin/omp-voice-controller:3578-3669`): `floor` = median of `tts_rms_floor` (recent speaker-bleed rms), `gate = max(320.0, floor*2.4)`, `hot = vad ≥ 0.55 AND rms ≥ gate AND past cooldown`. Hold opens after **3 consecutive** hot frames (`tts_loud_run >= 3`).
- Duck: `duck_output_volume()` (`:1778`) — gated by env `OMP_VOICE_DUCK_VOLUME` (plist sets 20), a `duck-off` marker in `STATE_DIR` (used by auto probes), and `state.tts_duck_restore` idempotency. Restore: `restore_output_volume()` (`:1807`).
- Restore paths: `note_barge_release()` (called at clip rejected / empty hold / whisper "not a stop", `:3449, 3713, 3718, 3728`), stop branch `apply_whisper` (`:3425`), watchdog in the `tts_barge_waiting` early-return (`:3621-3631`, 8 s), SIGTERM/SIGINT handler and loop exit (`:4298, 4369`).

## What is already shipped (commit `aa73e36`, live tree, tests green: 320 pytest + 114 node)
- Duck no longer fires at hold-open; it requires **5 consecutive hot frames (~0.4 s) at ≥ 1.5× the gate** (`DUCK_MIN_HOT_FRAMES=5`, `DUCK_MIN_RMS_FACTOR=1.5`, constants at `:138-146`).
- Duck/restore **ramp** over 4 osascript writes (`_ramp_output_volume`, `:1767`) instead of one jump.
- Watchdog: if a hold stays in `tts_barge_waiting` > 8 s, volume is restored.
- Regression tests in `tests/test_barge_fixture.py`: short "Stop." fixture holds but does not duck; sustained burst ducks with exact ramp `[57,45,32,20]`; stuck-waiting hold is restored by the watchdog.

## What is still broken / unproven
1. **The live controller is running the new tree.** Restart confirmed: pid **71979**, state IDLE (status.json). Re-run the E probe (`scripts/run_human_barge_probe.py`, `--auto` mode exists) before judging behavior.
2. **Gate floor is bleed-relative, not absolute.** `gate = max(320, floor*2.4)`. When the system is already ducked, bleed floor collapses (measured floor 42), so the gate stays 320 and moderate room sound still opens holds → repeated duck/restore flicker. A hysteresis or absolute floor (e.g. gate never below ~500 while ducked) may be needed.
3. **Restore uses osascript `set volume output volume` — master volume of the machine** — not per-app. The ramp does `output_volume()` read + 4 writes; each osascript call is ~30-80 ms, and restore re-reads the volume. If the read fails (`output_volume()` → None) the restore falls back to a single write; if osascript itself fails (permission/focus flake), `tts_duck_restore` stays set and the next duck is a no-op → **stays ducked**. No retry on failed restore exists.
4. **Latency chain** (measured, auto4 PASS): burst onset → hold +0.9-2.3 s → clip 16 frames (1.28 s) → tiny.en (~1 s) → stop. Stop decision takes 3-4 s total; owner perceives "volume dipped, speech kept going." The perceived flicker is mostly this 3-4 s decision window.
5. **tiny.en mis-transcribes human barges**: real clips of "hey jarvis stop" transcribed as "Thank you for watching.", "You can get it in the home voice control.", "Hey Jarvis." (never "stop"). Offline Handy/Qwen3-ASR (`/Applications/Handy.app/Contents/MacOS/handy --transcribe-file <wav> --json`) on the same clips also fails ("The Marimba click then.", "Asian."). `_is_playback_barge` (`:2260+`) accepts only all-"stop" tokens or verbatim "hold on a second" spans. So real human barges often reach the *decision* and get classified as "not a stop" — that is a detection gap, separate from ducking.

## Direction the next agent should evaluate (not decided)
- **Separate "duck decision" from "stop decision" entirely:** duck only when the burst is both sustained (≥5 hot frames) AND the clip is likely a human voice (peak ≥ some absolute rms, e.g. 700), and never duck again within a cooldown (e.g. 5 s) after a "not a stop" release.
- **Make restore bulletproof:** on failed `_run_osascript` restore, keep `tts_duck_restore` and retry on the next frame instead of clearing state; add a global periodic check in the main loop (not only inside `tts_barge_waiting`) that restores if ducked while no hold is open.
- **Floor hysteresis while ducked:** when ducked, freeze the floor/gate at pre-duck values so the collapsed bleed does not lower the gate and re-open holds.
- **Verify against the E acceptance criteria** (scenario doc §7): audible stop ≤ 1.2 s, no resume of cut text, next turn plays, owner verdict verbatim — row is permanent `NEEDS_HUMAN_APPROVAL`; auto runs supply measurements only.
- **Do not weaken existing gates** (AEC correlation guard 0.55, hold 3 frames, clip 16 frames/flush rules); fix the duck policy around them.

## Owner test protocol for the E/G/A6 rows (schedule with Akshay)
- **E (human barge):** run `scripts/run_human_barge_probe.py` (no `--auto`). Before launching, tell Akshay: one marimba click = reply live → say "hey jarvis stop". Keep the root owner session silent during the window (its spoken replies contaminate the clip; this caused the auto3 garbage transcripts). Collect his verbatim verdict with the `ask` tool; record in scenario doc §7 E line and flip `docs/testing/INDEX.md` line 188. E/G/A6 are permanent `NEEDS_HUMAN_APPROVAL` — never auto-pass.
- **G (10-min eyes-off task):** eyes-off soak while a reply plays; owner confirms nothing was mis-stopped mid-task.
- **A6 (double-talk):** `scripts/run_double_talk_probe.py`; owner gives a verbatim transcript of what he heard vs what the system did.
- Run all three with the controller restarted from the current HEAD so the ramped duck is loaded (verify pid via `~/.local/bin/omp-voice-controller status`).

## Key evidence files
- `.local/voice-agent/runs/VA-QUALITY-001-E-HUMAN-BARGE.json` (auto4 PASS: hold +2.35 s rms 1006, whisper "Hold on a second.", stop 3.798 s; owner_verdict null)
- `~/.local/state/omp-voice/barge-trace.jsonl` human run 2026-11-16 22:45 UTC: holds at rms 1966/2141/1093/2287 → ducks → all whispers garbage → `resume reason="not a stop"` ×3
- Clip dumps `~/.local/state/omp-voice/barge-clips/1794869161.528.wav`, `1794869292.340.wav`, `1794869312.707.wav` (tiny.en and Handy both fail on them)
- Tests: `tests/test_barge_fixture.py` (6 passing duck tests)
