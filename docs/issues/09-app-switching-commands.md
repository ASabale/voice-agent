# 09 — App switching by voice

Depends on 06 (actuator). Same pattern as 07: recognition in the command matcher, effect through `MacActuator`.

Status: done 2026-11-22. `previous_app` rows and a `tail`-bearing `switch_to_app`
row in `grammar.json` ("up to N free words after the slots"), mirrored in
`matchCommand` in `extension/voicebox-speech.ts`; `MacActuator.known_apps()` /
`resolve_app()` / `activate()` do the name lookup (`open -a`) over running
processes plus `.app` bundles, cached and refreshed on a miss. An unresolvable
name logs `app_not_found` to unmatched.jsonl and the words stay dictation.
Controller restarted (pid 60526), status IDLE.

## Goal
| Action | Example phrases | Effect |
|---|---|---|
| previous_app | "switch app", "previous app", "last app" | ⌘Tab (single tap, returns to most recent app) |
| switch_to_app | "switch to Chrome", "go to terminal", "open Slack", "hey jarvis can you switch to Visual Studio Code" | Activate the named app |

## Resolving the name
- Free-form tail after "switch to" / "go to" / "open" is not expressible in fixed slots; recognise it the way `_SCROLL_RE` was (one regex/matcher next to `match_command`), keeping a single place that maps transcript → action.
- Candidates: running regular apps (System Events) plus `.app` bundles in /Applications, /System/Applications, ~/Applications. Match case-insensitive, ignoring punctuation and a trailing "app"; prefer exact, then prefix, then a small alias map (chrome → Google Chrome, vs code / code → Visual Studio Code, terminal, finder, settings → System Settings). Lookup must be cheap: cache the bundle list, refresh on miss.
- Activate via `open -a <resolved name>` (launches if not running) through the actuator; recording adapter records `("activate", name)`.
- No match → NO action (the words stay normal dictation, nothing typed is lost) and log to unmatched.jsonl. This guards dictation that ends with "go to the store".

## Constraints
- Existing actions and the "go back"/"go forward" rows keep their behaviour ("go back" must not resolve as an app).
- TS `matchCommand` mirror: switch_to_app/previous_app must return noop there too; keep `tests/command_vectors.json` shared.
- Chime fires on success as with other actuator actions.

## Acceptance
- Table test through RecordingActuator with an injected app list: phrases above with bare / "hey jarvis" / "can you" prefixes; alias, prefix and case variants; unknown app → no action + unmatched log; "go back" still → go_back; dictation ending "go to the store" → no action.
- `~/.local/share/omp-voice/venv/bin/python -m pytest tests -q` and `node --experimental-strip-types --test tests/match_command.test.ts tests/voicebox-refusal.test.ts` green.
- Controller restarted per skill restart-voice-controller; status IDLE.
