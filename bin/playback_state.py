"""Playback slot semantics, shared by the controller and its tests.

A playback slot is one file in `<state>/tts-playing/<session-pid>.json`
written by the VoiceBox extension. This module answers "is this slot
speaking, which slot renders, how far into the file is afplay?" without
touching audio, files, or processes. Everything that opens a WAV, spawns
`afplay`, or subtracts samples lives in `bin/omp-voice-controller`.
Keeping the decision rules here is what makes the vectors in
`tests/playback_vectors.json` the complete contract for slot state.
"""

from __future__ import annotations

PLAYBACK_LEASE_SECONDS = 60.0
# An orphan afplay (writer dead, player alive) is trusted while its clip is
# still running: started_at plus the reference clip's real-time duration, plus
# slack for spawn lag. Without a reference, the flat 60 s cap still applies.
ORPHAN_LEASE_SLACK_SECONDS = 5.0


def orphan_lease_expiry(slot: dict) -> float:
    """When an orphaned afplay's echo can be considered finished."""
    try:
        started = float(slot.get("started_at") or 0)
    except (TypeError, ValueError):
        started = 0.0
    ref = slot_reference(slot)
    if ref is None:
        return started + PLAYBACK_LEASE_SECONDS
    duration = ref["frames"] / ref["sample_rate"] / playback_rate_of(slot)
    return started + duration + ORPHAN_LEASE_SLACK_SECONDS


def slot_reference(slot: dict) -> dict | None:
    """The WAV afplay is playing, as published on the playback slot.

    This is the render description. It is not echo cancellation.
    """
    if not isinstance(slot, dict):
        return None
    ref = slot.get("reference")
    if not isinstance(ref, dict):
        return None
    rate = ref.get("sample_rate")
    channels = ref.get("channels")
    frames = ref.get("frames")
    wav = ref.get("wav")
    if isinstance(rate, bool) or not isinstance(rate, int) or rate < 8000:
        return None
    if isinstance(channels, bool) or not isinstance(channels, int) or channels <= 0:
        return None
    if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
        return None
    if not isinstance(wav, str) or not wav.endswith(".wav"):
        return None
    return {"sample_rate": rate, "channels": channels, "frames": frames, "wav": wav}


def playback_rate_of(slot: dict) -> float:
    """afplay -r for this clip. Missing or out of range means 1x.

    The voice command accepts 0.7 to 2.0. The default in the extension is 1.18.
    """
    if not isinstance(slot, dict):
        return 1.0
    raw = slot.get("playback_rate")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 1.0
    rate = float(raw)
    if rate < 0.7 or rate > 2.0:
        return 1.0
    return rate


def render_cursor(started_at: float, now: float, sample_rate: int, playback_rate: float = 1.0) -> int:
    """How many file samples afplay has consumed since the clip started."""
    if sample_rate <= 0 or playback_rate <= 0 or now <= started_at:
        return 0
    return int((now - started_at) * sample_rate * playback_rate)


def _valid_pid(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _slot_rank(slot: dict) -> tuple[float, int, int]:
    started = slot.get("started_at")
    try:
        started_f = float(started) if isinstance(started, (int, float)) and not isinstance(started, bool) else 0.0
    except (TypeError, ValueError):
        started_f = 0.0
    turn = slot.get("turn")
    clip = slot.get("clip")
    turn_i = turn if isinstance(turn, int) and not isinstance(turn, bool) else -1
    clip_i = clip if isinstance(clip, int) and not isinstance(clip, bool) else -1
    return (started_f, turn_i, clip_i)


def choose_render_slot(slots, now: float, pid_alive_fn) -> dict | None:
    """Newest slot that is speaking and names a WAV. Directory order is not used."""
    chosen = None
    best: tuple[float, int, int] | None = None
    for slot in slots:
        if not isinstance(slot, dict) or slot_reference(slot) is None:
            continue
        if not slot_is_speaking(slot, now, pid_alive_fn, 0.0):
            continue
        rank = _slot_rank(slot)
        if best is None or rank > best:
            best = rank
            chosen = slot
    return chosen


def slot_is_speaking(slot: dict, now: float, pid_alive_fn, tail: float) -> bool:
    """One session slot. A dead afplay is silence. A clean end keeps the reverb tail."""
    if not isinstance(slot, dict):
        return False
    ended_raw = slot.get("ended_at")
    try:
        ended = float(ended_raw) if ended_raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        ended = 0.0
    if slot.get("playing") is not True:
        return ended > 0 and (now - ended) < tail
    afplay = _valid_pid(slot.get("afplay_pid"))
    writer = _valid_pid(slot.get("writer_pid"))
    if afplay is not None:
        if not pid_alive_fn(afplay):
            return False
        if writer is not None and not pid_alive_fn(writer):
            return now < orphan_lease_expiry(slot)
        return True
    if writer is None or not pid_alive_fn(writer):
        return False
    try:
        lease = float(slot.get("lease_until") or 0)
    except (TypeError, ValueError):
        lease = 0.0
    return now < lease


def playback_is_speaking(data: dict, now: float, pid_alive_fn, tail: float) -> bool:
    """Legacy files have no sessions object and do not check pids."""
    if not isinstance(data, dict):
        return False
    sessions = data.get("sessions")
    if isinstance(sessions, dict):
        return any(
            isinstance(slot, dict) and slot_is_speaking(slot, now, pid_alive_fn, tail)
            for slot in sessions.values()
        )
    if data.get("playing") is True and not data.get("ended_at"):
        return True
    try:
        ended = float(data.get("ended_at", 0) or 0)
    except (TypeError, ValueError):
        return False
    return ended > 0 and (now - ended) < tail


def playback_sources_speaking(slots, legacy, now: float, pid_alive_fn, tail: float) -> bool:
    """slots is None only when the tts-playing directory is absent."""
    if slots is not None:
        return any(
            isinstance(slot, dict) and slot_is_speaking(slot, now, pid_alive_fn, tail) for slot in slots
        )
    if not isinstance(legacy, dict):
        return False
    return playback_is_speaking(legacy, now, pid_alive_fn, tail)


def project_aggregate(slots, pid_alive_fn=None, now: float | None = None, tail: float = 0.0) -> dict:
    """The flat tts-playing.json projection the old reader (and the memory
    guardian) understands, derived from the session slots.

    With pid_alive_fn, a slot counts as live by the same rule slot_is_speaking
    uses (afplay alive, or writer alive while the lease holds). Without it the
    caller promises the slots are already liveness-checked, so the legacy
    flag-only behavior stands.
    """
    if pid_alive_fn is None:
        live = [slot for slot in slots if isinstance(slot, dict) and slot.get("playing") is True]
    else:
        if now is None:
            import time as _time

            now = _time.time()
        live = [slot for slot in slots if slot_is_speaking(slot, now, pid_alive_fn, tail)]
    if live:
        def started_at(slot: dict) -> float:
            value = slot.get("started_at")
            return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0

        pick = max(live, key=started_at)
        out: dict = {"playing": True}
        if isinstance(pick.get("started_at"), (int, float)) and not isinstance(pick.get("started_at"), bool):
            out["started_at"] = pick["started_at"]
        pid = _valid_pid(pick.get("afplay_pid"))
        if pid is not None:
            out["pid"] = pid
        return out
    ended = 0.0
    for slot in slots:
        if isinstance(slot, dict):
            value = slot.get("ended_at")
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > ended:
                ended = value
    out = {"playing": False}
    if ended > 0:
        out["ended_at"] = ended
    return out
