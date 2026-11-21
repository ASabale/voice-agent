"""Live Handy flags. subprocess is stubbed, so history.db is not written."""

import importlib.machinery
import importlib.util
import queue
import sys
import time
import types
from pathlib import Path

import numpy as np
import pytest

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_handy", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


class _Completed:
    returncode = 0
    stdout = ""


def _install(monkeypatch: pytest.MonkeyPatch, running: bool) -> list[list[str]]:
    calls: list[list[str]] = []

    def _run(args: list[str], **_kwargs: object) -> _Completed:
        calls.append(list(args))
        return _Completed()

    monkeypatch.setattr(controller.subprocess, "run", _run)
    monkeypatch.setattr(controller, "handy_process_running", lambda: running)
    monkeypatch.setattr(controller, "unmute_async", lambda: None)
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)
    return calls


def test_cancel_stop_and_fresh_start_use_the_live_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    assert controller.handy_cancel() is True
    assert controller.handy_stop_recording() is True
    assert controller.handy_start_recording(fresh=True) is True
    assert calls == [
        [controller.HANDY_BIN, "--cancel"],
        [controller.HANDY_BIN, "--toggle-transcription"],
        [controller.HANDY_BIN, "--toggle-transcription"],
    ]


def test_a_restarted_recording_cancels_before_the_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    assert controller.handy_start_recording(fresh=False) is True
    assert calls == [
        [controller.HANDY_BIN, "--cancel"],
        [controller.HANDY_BIN, "--toggle-transcription"],
    ]


def test_a_stopped_app_is_not_launched(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=False)
    assert controller.handy_cancel() is False
    assert controller.handy_stop_recording() is False
    assert controller.handy_start_recording(fresh=True) is False
    assert controller.handy_start_recording(fresh=False) is False
    assert calls == []


def test_only_an_allowed_launch_starts_a_missing_app(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=False)
    assert controller.handy_start_recording(allow_launch=True, fresh=True) is True
    assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]


def test_file_mode_wake_does_not_toggle_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    monkeypatch.setenv("OMP_VOICE_HANDY", "transcribe-file")
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    monkeypatch.setattr(controller, "play_cue", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "write_status", lambda *_args, **_kwargs: None)

    def _forbid_thread(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("thread")

    monkeypatch.setattr(controller.threading, "Thread", _forbid_thread)

    class _Model:
        def reset(self) -> None:
            return None

        def reset_states(self) -> None:
            return None

    mic = controller.MicState()
    mic.enter_dictating("test wake", _Model(), _Model())
    assert mic.state == "DICTATING"
    assert calls == []


class _Reset:
    def reset(self) -> None:
        return None

    def reset_states(self) -> None:
        return None


def test_one_flush_toggles_handy_once_and_submits_the_final_text(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    posted: list[str] = []

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "sent"}

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "Ship the notes."))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "handy_start_recording",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    assert posted == ["Ship the notes."]
    assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]
    assert mic.state == "IDLE"


def test_a_cancelled_flush_returns_to_idle_without_starting_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    posted: list[str] = []
    cues: list[str] = []

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "cancelled", "draft": "Ship the notes. ship please", "strippedCommand": "cancel"}

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "cancel"))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "handy_start_recording",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    assert posted == ["cancel"]
    assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]
    assert cues == [controller.SOUND_CANCEL]
    assert mic.state == "IDLE"


def test_a_held_send_flush_stays_dictating_and_keeps_both_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    posted: list[str] = []
    injected: list[tuple[str, str]] = []
    status: list[tuple[str, dict]] = []
    starts = 0

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "held", "draft": "Ship the notes. ship please"}

    def start(*_a: object, **_k: object) -> bool:
        nonlocal starts
        starts += 1
        return True

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "ship all done"))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda state, payload: status.append((state, payload)))
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", start)
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        mic = controller.MicState()
        mic.state = "DICTATING"
        mic.speech_seen_in_chunk = True
        now = 100.0
        mic.chunk_started_at = now
        mic.last_handy_ui_check = now
        mic.last_speech_at = now - 10
        mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
        mic.handle_dictating_frame(
            np.zeros(1280, dtype=np.int16),
            now,
            0.0,
            0.0,
            False,
            _Reset(),
            _Reset(),
            5.0,
            15.0,
            queue.Queue(),
        )
        assert mic.state == "DICTATING"
        assert posted == ["ship all done"]
        assert starts == 1
        assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        # The status payload also carries turn latency metadata; only the
        # state transition and the action are contractual here.
        assert [(state, fields["last_action"]) for state, fields in status] == [("DICTATING", "held")]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_an_appended_flush_records_appended_and_stays_dictating(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    posted: list[str] = []
    status: list[tuple[str, dict]] = []
    starts = 0

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "appended", "draft": "Thanks."}

    def start(*_a: object, **_k: object) -> bool:
        nonlocal starts
        starts += 1
        return True

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "Thanks."))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda state, payload: status.append((state, payload)))
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", start)
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("inject")),
    )
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    assert mic.state == "DICTATING"
    assert posted == ["Thanks."]
    assert starts == 1
    assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]
    assert [(state, fields["last_action"]) for state, fields in status] == [("DICTATING", "appended")]


def test_an_older_history_read_does_not_replace_the_consumed_flush_row(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    posted: list[str] = []
    latest = {"id": 0, "text": ""}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "appended", "draft": text}

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "Thanks."))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (latest["id"], latest["text"]))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", lambda *_a, **_k: True)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "fallback_macos_inject",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.last_history_id = 3
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    frame = np.zeros(1280, dtype=np.int16)
    mic.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["Thanks."]
    assert mic.last_history_id == 8

    latest["id"] = 8
    latest["text"] = "Thanks."
    mic.handle_dictating_frame(frame, now + 0.1, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["Thanks."]
    assert mic.last_history_id == 8
    assert mic.state == "DICTATING"


def test_chunk_restart_timing_follows_the_frame_clock_not_wall_monotonic(monkeypatch: pytest.MonkeyPatch) -> None:
    """VA-CI-002: on a fresh CI runner `time.monotonic()` is ~85 s of uptime, far
    from the synthetic frame timeline. If a flush restart resets chunk timing
    against a clock the caller cannot control, the next frame trips the 15 s idle
    timeout and cancels a dictation that just succeeded."""
    _install(monkeypatch, running=True)
    posted: list[str] = []
    latest = {"id": 0, "text": ""}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "appended", "draft": text}

    monkeypatch.setattr(
        controller,
        "time",
        types.SimpleNamespace(monotonic=lambda: 85.0, time=time.time, sleep=lambda _s: None, strftime=time.strftime),
    )
    monkeypatch.setattr(controller.sqlite3, "connect", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("history.db")))
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "Thanks."))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (latest["id"], latest["text"]))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", lambda *_a, **_k: True)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "fallback_macos_inject",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.last_history_id = 3
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    frame = np.zeros(1280, dtype=np.int16)
    mic.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["Thanks."]
    assert mic.chunk_started_at == now
    latest["id"] = 8
    latest["text"] = "Thanks."
    mic.handle_dictating_frame(frame, now + 0.1, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert mic.state == "DICTATING"


def test_an_older_history_read_does_not_repeat_a_scratched_flush_row(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    posted: list[str] = []
    starts = 0
    latest = {"id": 0, "text": ""}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "scratched", "draft": text}

    def start(*_a: object, **_k: object) -> bool:
        nonlocal starts
        starts += 1
        return True

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "scratch that"))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (latest["id"], latest["text"]))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", start)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "fallback_macos_inject",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.last_history_id = 3
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    frame = np.zeros(1280, dtype=np.int16)
    mic.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["scratch that"]
    assert starts == 1
    assert mic.last_history_id == 8
    assert mic.state == "DICTATING"

    latest["id"] = 8
    latest["text"] = "scratch that"
    mic.handle_dictating_frame(frame, now + 0.1, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["scratch that"]
    assert starts == 1
    assert mic.last_history_id == 8


def test_an_older_history_read_does_not_repeat_a_cleared_flush_row(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    posted: list[str] = []
    starts = 0
    latest = {"id": 0, "text": ""}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "cleared", "draft": text}

    def start(*_a: object, **_k: object) -> bool:
        nonlocal starts
        starts += 1
        return True

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "clear draft"))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (latest["id"], latest["text"]))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", start)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "fallback_macos_inject",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.last_history_id = 3
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    frame = np.zeros(1280, dtype=np.int16)
    mic.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["clear draft"]
    assert starts == 1
    assert mic.last_history_id == 8
    assert mic.state == "DICTATING"

    latest["id"] = 8
    latest["text"] = "clear draft"
    mic.handle_dictating_frame(frame, now + 0.1, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["clear draft"]
    assert starts == 1
    assert mic.last_history_id == 8


def test_a_newer_history_row_is_dispatched_once_after_the_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    posted: list[str] = []
    reads = {"n": 0}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "appended", "draft": text}

    def latest() -> tuple[int, str]:
        reads["n"] += 1
        if reads["n"] == 1:
            return (3, "")
        return (9, "Next line.")

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "Thanks."))
    monkeypatch.setattr(controller, "latest_history_row", latest)
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", lambda *_a, **_k: True)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "fallback_macos_inject",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.last_history_id = 3
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    frame = np.zeros(1280, dtype=np.int16)
    mic.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["Thanks."]
    assert mic.last_history_id == 8

    mic.handle_dictating_frame(frame, now + 0.1, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["Thanks.", "Next line."]
    assert mic.last_history_id == 9

    mic.handle_dictating_frame(frame, now + 0.2, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["Thanks.", "Next line."]
    assert mic.state == "DICTATING"


def test_a_newer_history_row_is_dispatched_once_after_a_scratch_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    posted: list[str] = []
    reads = {"n": 0}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        if text == "scratch that":
            return {"action": "scratched", "draft": text}
        return {"action": "appended", "draft": text}

    def latest() -> tuple[int, str]:
        reads["n"] += 1
        if reads["n"] == 1:
            return (3, "")
        return (9, "Next line.")

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "scratch that"))
    monkeypatch.setattr(controller, "latest_history_row", latest)
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", lambda *_a, **_k: True)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "fallback_macos_inject",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.last_history_id = 3
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    frame = np.zeros(1280, dtype=np.int16)
    mic.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["scratch that"]
    assert mic.last_history_id == 8
    assert mic.state == "DICTATING"

    mic.handle_dictating_frame(frame, now + 0.1, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["scratch that", "Next line."]
    assert mic.last_history_id == 9

    mic.handle_dictating_frame(frame, now + 0.2, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["scratch that", "Next line."]


def test_a_newer_history_row_is_dispatched_once_after_a_clear_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    posted: list[str] = []
    reads = {"n": 0}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        if text == "clear draft":
            return {"action": "cleared", "draft": text}
        return {"action": "appended", "draft": text}

    def latest() -> tuple[int, str]:
        reads["n"] += 1
        if reads["n"] == 1:
            return (3, "")
        return (9, "Next line.")

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "clear draft"))
    monkeypatch.setattr(controller, "latest_history_row", latest)
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", lambda *_a, **_k: True)
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "fallback_macos_inject",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.last_history_id = 3
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    frame = np.zeros(1280, dtype=np.int16)
    mic.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["clear draft"]
    assert mic.last_history_id == 8
    assert mic.state == "DICTATING"

    mic.handle_dictating_frame(frame, now + 0.1, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["clear draft", "Next line."]
    assert mic.last_history_id == 9

    mic.handle_dictating_frame(frame, now + 0.2, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert posted == ["clear draft", "Next line."]


class _Now:
    def __init__(self, target) -> None:
        self._target = target

    def start(self) -> None:
        self._target()


def test_idle_timeout_cancels_handy_and_the_next_wake_starts_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    posts: list[str] = []

    def bridge(_path: str, method: str = "GET", body: dict | None = None, base: str | None = None) -> dict[str, str]:
        posts.append(str((body or {}).get("text")))
        return {"action": "scratched"}

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    monkeypatch.setattr(controller.threading, "Thread", lambda target, daemon=True: _Now(target))
    monkeypatch.setattr(
        controller,
        "dispatch_transcript",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("submit")),
    )

    mic = controller.MicState()
    mic.state = "DICTATING"
    now = 100.0
    mic.chunk_started_at = now - 15
    mic.last_handy_ui_check = now
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    assert mic.state == "IDLE"
    assert posts == []
    assert calls == [[controller.HANDY_BIN, "--cancel"]]

    mic.enter_dictating("second wake", _Reset(), _Reset())
    assert mic.state == "DICTATING"
    assert calls == [
        [controller.HANDY_BIN, "--cancel"],
        [controller.HANDY_BIN, "--toggle-transcription"],
    ]


def test_file_mode_idle_timeout_does_not_cancel_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    monkeypatch.setenv("OMP_VOICE_HANDY", "transcribe-file")
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(
        controller,
        "bridge_request",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("bridge")),
    )
    mic = controller.MicState()
    mic.state = "DICTATING"
    now = 100.0
    mic.chunk_started_at = now - 15
    mic.last_handy_ui_check = now
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    assert mic.state == "IDLE"
    assert calls == []


def test_cancel_that_stops_once_scratches_and_does_not_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    posts: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, base: str | None = None) -> dict[str, str] | None:
        text = str((body or {}).get("text", ""))
        posts.append((method, text))
        if text == "cancel that":
            raise AssertionError("submit")
        if text == "scratch that":
            return {"action": "scratched", "ok": True}
        return None

    def _db(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("history.db")

    monkeypatch.setattr(controller.sqlite3, "connect", _db)
    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(controller, "resolve_delivery", lambda: {"mode": "none", "focused_text": False})
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (9, "cancel that"))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")))
    monkeypatch.setattr(controller.threading, "Thread", lambda target, daemon=True: _Now(target))

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    assert mic.state == "IDLE"
    assert [item for item in posts if item[0] == "POST"] == []
    assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]

    mic.enter_dictating("next wake", _Reset(), _Reset())
    assert mic.state == "DICTATING"
    assert calls == [
        [controller.HANDY_BIN, "--toggle-transcription"],
        [controller.HANDY_BIN, "--toggle-transcription"],
    ]


class _Score:
    def __init__(self, score: float) -> None:
        self.score = score

    def predict(self, _frame: np.ndarray) -> dict[str, float]:
        return {"hey_jarvis": self.score}

    def reset(self) -> None:
        return None

    def reset_states(self) -> None:
        return None


def _cancel_then(monkeypatch: pytest.MonkeyPatch) -> tuple[list[list[str]], controller.MicState]:
    calls = _install(monkeypatch, running=True)

    def bridge(path: str, method: str = "GET", body: dict | None = None, base: str | None = None) -> dict[str, str] | None:
        text = str((body or {}).get("text", ""))
        if text == "cancel that":
            raise AssertionError("submit")
        if text == "scratch that":
            return {"action": "scratched", "ok": True}
        return None

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(controller, "resolve_delivery", lambda: {"mode": "none", "focused_text": False})
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (9, "cancel that"))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")))
    monkeypatch.setattr(controller, "refresh_render_reference", lambda: None)
    monkeypatch.setattr(controller, "cancel_playback_echo", lambda frame, captured_at=None: frame)
    monkeypatch.setattr(controller.threading, "Thread", lambda target, daemon=True: _Now(target))
    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    mic.partial_shown = "Ship the notes."
    mic.partial_base = "http://127.0.0.1:9"
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    return calls, mic


def test_a_wake_during_cancel_cooldown_starts_one_recording(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, mic = _cancel_then(monkeypatch)
    assert mic.state == "IDLE"
    assert mic.cooldown_until > controller.time.monotonic()
    frame = np.zeros(1280, dtype=np.int16)
    low = _Score(0.1)
    controller.handle_captured_frame(
        mic, frame, None, "fixture", low, low, 0.4, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue()
    )
    assert mic.state == "IDLE"
    assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]
    heard = _Score(0.91)
    controller.handle_captured_frame(
        mic, frame, None, "fixture", heard, heard, 0.4, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue()
    )
    assert mic.state == "DICTATING"
    assert calls == [
        [controller.HANDY_BIN, "--toggle-transcription"],
        [controller.HANDY_BIN, "--toggle-transcription"],
    ]


def test_a_dismissed_wake_stays_closed_during_cancel_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, mic = _cancel_then(monkeypatch)
    mic.score_wake_blocked_until = controller.time.monotonic() + 30
    heard = _Score(0.91)
    controller.handle_captured_frame(
        mic,
        np.zeros(1280, dtype=np.int16),
        None,
        "fixture",
        heard,
        heard,
        0.4,
        "hey_jarvis",
        0.5,
        5.0,
        15.0,
        queue.Queue(),
    )
    assert mic.state == "IDLE"
    assert calls == [[controller.HANDY_BIN, "--toggle-transcription"]]


def test_a_failed_status_holds_the_flush_once_and_does_not_type(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install(monkeypatch, running=True)
    posts: list[tuple[str, str]] = []
    controller._undelivered_transcript = ""

    def bridge(path: str, method: str = "GET", body: dict | None = None, base: str | None = None) -> None:
        posts.append((method, str((body or {}).get("text", ""))))
        return None

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (4, "Ship the notes."))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")),
    )
    monkeypatch.setattr(
        controller.sqlite3,
        "connect",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("history.db")),
    )

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    now = 50.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    assert mic.state == "DICTATING"
    assert controller._undelivered_transcript == "Ship the notes."
    assert posts == [("GET", "")]
    assert calls == [
        [controller.HANDY_BIN, "--toggle-transcription"],
        [controller.HANDY_BIN, "--cancel"],
        [controller.HANDY_BIN, "--toggle-transcription"],
    ]
    again = controller.dispatch_transcript("Ship the notes.")
    assert again == {"action": "held", "draft": "Ship the notes."}
    assert controller._undelivered_transcript == "Ship the notes."

    posted: list[str] = []

    def restored(path: str, method: str = "GET", body: dict | None = None, base: str | None = None) -> dict:
        if method == "GET":
            return {"ok": True, "version": 2, "draft": ""}
        posted.append(str((body or {}).get("text", "")))
        return {"ok": True, "action": "appended", "draft": posted[-1]}

    monkeypatch.setattr(controller, "bridge_request", restored)
    delivered = controller.dispatch_transcript("Thanks.")
    assert delivered.get("draft") == "Ship the notes. Thanks."
    assert posted == ["Ship the notes. Thanks."]
    assert controller._undelivered_transcript == ""


# --- VA-LAT-001: turn latency fields (wake_to_flush_s, asr_s, dispatch_s,
# stop_latency_s, turn_seq), all on time.monotonic(). ---


def test_a_wake_resets_stale_turn_latencies_and_bumps_turn_seq(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    monkeypatch.setenv("OMP_VOICE_HANDY", "transcribe-file")
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)

    mic = controller.MicState()
    mic.enter_dictating("wake one", _Reset(), _Reset())
    first = mic.turn_metrics()
    assert first["turn_seq"] == 1
    assert first["wake_to_flush_s"] is None
    assert first["asr_s"] is None
    assert first["dispatch_s"] is None

    # A finished turn's numbers must not leak into the status of the next one.
    mic.flush_mono = mic.wake_mono + 7.2
    mic.asr_s = 0.41
    mic.dispatch_s = 0.03
    mic.stop_latency_s = 0.6
    mic.enter_dictating("wake two", _Reset(), _Reset())
    second = mic.turn_metrics()
    assert second["turn_seq"] == 2
    assert second["wake_to_flush_s"] is None
    assert second["asr_s"] is None
    assert second["dispatch_s"] is None
    # stop_latency_s is the last barge stop, not a per-dictation-turn value.
    assert second["stop_latency_s"] == 0.6


def test_a_flushed_turn_publishes_fresh_latencies_in_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, running=True)
    posted: list[str] = []
    status: list[tuple[str, dict]] = []

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "appended", "draft": "ship all done"}

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (8, "ship all done"))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda state, payload: status.append((state, payload)))
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "handy_start_recording", lambda *_a, **_k: True)
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("inject")),
    )
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )

    mic = controller.MicState()
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    mic.enter_dictating("wake", _Reset(), _Reset())
    now = 100.0
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.speech_seen_in_chunk = True
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        0.0,
        0.0,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )
    turn = status[-1][1]["turn"]
    assert turn == mic.turn_metrics()
    assert turn["turn_seq"] == 1
    assert turn["wake_to_flush_s"] is not None and turn["wake_to_flush_s"] >= 0
    assert turn["asr_s"] is not None and turn["asr_s"] >= 0
    assert turn["dispatch_s"] is not None and turn["dispatch_s"] >= 0
    assert turn["stop_latency_s"] is None  # no barge happened in this test


def test_stop_playback_returns_the_confirmed_death_time(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {"n": 0}

    def alive(_pid: int) -> bool:
        seen["n"] += 1
        return seen["n"] <= 1

    monkeypatch.setattr(controller, "_omp_vb_pids", lambda: ["4242"])
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    monkeypatch.setattr(controller, "pid_alive", alive)
    before = time.monotonic()
    died_at = controller.stop_playback("test stop")
    assert died_at is not None and died_at >= before
    assert seen["n"] >= 2, "stop_playback returned without confirming the clip process died"


def test_stop_playback_reports_none_when_a_clip_survives_the_kill(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(controller, "_omp_vb_pids", lambda: ["4242"])
    monkeypatch.setattr(controller, "silence_speech", lambda _abort: None)
    monkeypatch.setattr(controller, "pid_alive", lambda _pid: True)
    ticks = iter([1000.0, 1001.0, 1002.0])
    monkeypatch.setattr(controller.time, "monotonic", lambda: next(ticks))
    assert controller.stop_playback("test stop") is None


def test_barge_stop_latency_spans_hold_onset_to_death_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    onset = time.monotonic()

    def fake_stop(_reason: str) -> float:
        return onset + 0.579

    monkeypatch.setattr(controller, "stop_playback", fake_stop)
    mic = controller.MicState()
    mic.barge_onset_mono = onset
    mic.apply_whisper("tts_barge", "Stop.", _Reset(), None, queue.Queue())
    assert mic.stop_latency_s == 0.579
    assert mic.turn_metrics()["stop_latency_s"] == 0.579


def _flush_mic(mic: controller.MicState) -> None:
    now = 100.0
    mic.state = "DICTATING"
    mic.speech_seen_in_chunk = True
    mic.chunk_started_at = now
    mic.last_handy_ui_check = now
    mic.last_speech_at = now - 10
    mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16) for _ in range(10)]
    mic.handle_dictating_frame(
        np.zeros(1280, dtype=np.int16),
        now,
        1600.0,
        0.12,
        False,
        _Reset(),
        _Reset(),
        5.0,
        15.0,
        queue.Queue(),
    )


def _install_fallback(monkeypatch: pytest.MonkeyPatch, posted: list[str]) -> None:
    _install(monkeypatch, running=True)

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "appended"}

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: None)
    monkeypatch.setattr(controller, "handy_stop_recording", lambda: True)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(
        controller.MicState,
        "transcribe_local_fallback",
        lambda _self, _jobs, _frames: "Thank you.",
    )
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_cancel",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
        "handy_start_recording",
    ):
        monkeypatch.setattr(
            controller,
            name,
            lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)),
        )


def test_echo_only_chunk_discards_the_local_whisper_hallucination(monkeypatch: pytest.MonkeyPatch) -> None:
    """§2C: a chunk with no human-attributed frames never dispatches a fallback."""
    posted: list[str] = []
    _install_fallback(monkeypatch, posted)
    mic = controller.MicState()
    _flush_mic(mic)
    assert posted == []
    assert mic.state == "IDLE"


def test_attributed_chunk_keeps_the_local_fallback_transcript(monkeypatch: pytest.MonkeyPatch) -> None:
    """Five near-end frames of real speech let the fallback through."""
    posted: list[str] = []
    _install_fallback(monkeypatch, posted)
    mic = controller.MicState()
    mic.dict_human_frames = controller.DICT_HUMAN_MIN_FRAMES
    _flush_mic(mic)
    assert posted == ["Thank you."]
    assert mic.state == "IDLE"
