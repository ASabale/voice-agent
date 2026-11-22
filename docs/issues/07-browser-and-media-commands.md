# 07 — Browser and media commands (grammar rows)

Status: done 2026-11-22. 18 new grammar rows and actuator mappings; the TS mirror
(`matchCommand`) and `tests/command_vectors.json` cover them; unmatched command tails
append to `~/.local/state/omp-voice/unmatched.jsonl`.

Depends on 06.

## Goal
Add fixed-grammar commands executed through the actuator. Each command = one `grammar.json` action group + one actuator mapping. Suffix matching already lets "can you scroll to the end" match.

| Action | Example phrases | Effect |
|---|---|---|
| scroll_end / scroll_top | "scroll to the end/bottom", "scroll to the top" | End / Home |
| page_down / page_up | "page down", "page up" | Page keys |
| full_screen / exit_full_screen | "full screen", "exit full screen" | YouTube in Chrome (frontmost Chrome + youtube.com URL via AppleScript): `f`; otherwise ⌃⌘F. Exit: Escape on YouTube, else ⌃⌘F |
| play_video / pause_video | "play video", "pause video", "resume video" | Space (k on YouTube) |
| go_back / go_forward | "go back", "go forward" | ⌘[ / ⌘] |
| next_tab / previous_tab / new_tab / close_tab | "next tab", "previous tab", "new tab", "close tab" | ⌃Tab, ⌃⇧Tab, ⌘T, ⌘W |
| zoom_in / zoom_out | "zoom in", "zoom out" | ⌘= / ⌘- |

## Constraints
- Bare "pause"/"stop" already mean pause dictation (`paused`); do NOT change them. Video control requires the word "video" (or "play video"/"resume video").
- Existing actions (sent, paused, scratched, cleared, cancelled, scroll) keep current behaviour; existing tests stay green.
- Keep the TS extension `matchCommand` mirror consistent if it enumerates actions (check extension/).
- Log every unmatched transcript tail that came during command mode / looked like a command to a JSONL file under ~/.local/state/omp-voice/ (e.g. `unmatched.jsonl`) for later intent-layer data. Only if a clear hook exists; otherwise skip and note it.

## Acceptance
- Table-driven test: every phrase above (with and without "hey jarvis" and a "can you" prefix) → expected action → expected recorded actuator events.
- Collision test: "pause", "stop" still → `paused`.
- `python -m pytest tests -q` green.
