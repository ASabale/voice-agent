# 06 — Actuator module (move scroll onto it)

Status: done 2026-11-22. Actuator seam in `bin/omp-voice-controller` (`MacActuator` with
`RealActuator` and `RecordingActuator`); scroll and key chords run through `perform()`.
Verify: `~/.local/share/omp-voice/venv/bin/python -m pytest tests -q`.

Source: architecture review 2026-11-22, candidate 2 (Strong). Minimal-risk path: no LLM, no change to mic/wake/AEC/bridge.

## Goal
One module in the controller owns "do an action on the Mac": read frontmost app (bundle id), send the action, and be replaceable by a recording adapter in tests. Two adapters: real (CGEvent via the existing ctypes setup, osascript via `_run_osascript`) and recording.

## Scope
- Move existing scroll (`scroll_focus`, `_SCROLL_RE` execution path, CGEventCreateScrollWheelEvent2) onto the actuator. Recognition of "scroll up/down" stays as it is today.
- Add key-chord support (keycode + modifiers via CGEvent) — needed by ticket 07.
- Frontmost app lookup (NSWorkspace via osascript or ctypes) exposed by the actuator.
- Non-goals: paste/inject/backspace migration, playback, frame intake, delivery, any LLM.

## Acceptance
- Existing scroll behaviour unchanged live ("scroll down", "scroll up a lot").
- New tests: scroll and a key chord driven through the recording adapter assert the exact events emitted; no stubbed module globals.
- `python -m pytest tests -q` green.
