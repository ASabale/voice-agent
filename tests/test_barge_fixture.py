"""A short stop is paused, then Whisper hears it, before playback is allowed to resume.

The thresholds are unchanged. The stop fixture's third hot frame is the last
loud frame, so the old path resumed before recognition.
"""

import importlib.machinery
import importlib.util
import json
import queue
import sys
import wave
from pathlib import Path

import numpy as np
from openwakeword.vad import VAD

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_barge_fixture", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

_FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


class _OwwStub:
    def reset(self) -> None:
        return None

    def predict(self, _frame: np.ndarray) -> dict[str, float]:
        return {"hey_jarvis": 0.0}


def _wav(name: str) -> np.ndarray:
    with wave.open(str(_FIXTURES / name)) as handle:
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).copy()


def _feed(mic: controller.MicState, pcm: np.ndarray, jobs: queue.Queue, vad: VAD) -> None:
    pad = (-len(pcm)) % 1280
    if pad:
        pcm = np.concatenate([pcm, np.zeros(pad, dtype=np.int16)])
    pcm = np.concatenate([pcm, np.zeros(1280 * 6, dtype=np.int16)])

    class _Oww:
        def reset(self) -> None:
            return None

        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {"hey_jarvis": 0.0}

    for start in range(0, len(pcm), 1280):
        controller.handle_captured_frame(
            mic,
            pcm[start : start + 1280],
            controller.time.time(),
            "fixture",
            _Oww(),
            vad,
            0.40,
            "hey_jarvis",
            0.5,
            5.0,
            15.0,
            jobs,
        )


def test_stop_fixture_is_whispered_before_playback_can_resume(monkeypatch) -> None:
    pauses: list[str] = []
    resumes = 0
    stops: list[str] = []

    monkeypatch.setattr(controller, "pause_tts_clips", lambda: pauses.append("pause"))
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: resumes.__iadd__(1) or None)
    monkeypatch.setattr(controller, "stop_playback", lambda reason: stops.append(reason))
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    for name in ("silence_speech", "kill_tts_clips", "handy_start_recording", "dispatch_transcript", "play_cue", "write_status"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "resume_tts_clips", resume)
    vad = VAD()
    jobs: queue.Queue = queue.Queue(maxsize=1)
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    _feed(mic, _wav("stop-say.wav"), jobs, vad)
    assert pauses == []
    assert resumes == 0
    assert stops == []
    assert mic.tts_barge_waiting is True
    assert mic.whisper_pending is not None
    job = jobs.get_nowait()
    assert job["prompt"] == "Hey Jarvis. stop."
    peak = float(np.max(np.abs(job["audio"])))
    assert peak > 0.2
    mic.apply_whisper("tts_barge", "Stop.", None, vad, jobs)
    assert len(stops) == 1
    assert "Stop." in stops[0]
    assert resumes == 0
    assert mic.state == "IDLE"

    quiet = controller.MicState()
    quiet.last_manual_check = 1e12
    quiet.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    before = len(pauses)
    _feed(quiet, np.zeros(1280 * 10, dtype=np.int16), queue.Queue(maxsize=1), VAD())
    assert len(pauses) == before
    assert quiet.tts_barge_held is False


def test_holds_duck_the_speaker_and_release_restores_it(monkeypatch, tmp_path) -> None:
    """VA-PHYS-003 follow-up: a sustained loud hold ducks the speaker, every release restores it.

    The held clip is the Whisper evidence; with the reply loud, tiny.en heard
    garbage. Ducking the speaker during the hold makes the clip mostly the
    person. Duck is off unless OMP_VOICE_DUCK_VOLUME is set, and it waits for
    DUCK_MIN_HOT_FRAMES consecutive frames above 1.5x the gate so a short
    environmental sound never touches the volume.
    """
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)  # never read a live probe's duck-off marker
    osascript: list[str] = []
    current = {"volume": 70}

    class _Res:
        stdout = ""
        returncode = 0

    def fake_run(_cmd: list[str], **_kw: object) -> object:
        script = _cmd[2]
        osascript.append(script)
        res = _Res()
        if "output volume of" in script:
            res.stdout = str(current["volume"])
        else:
            current["volume"] = int(script.rsplit(" ", 1)[1])
            res.stdout = ""
        return res

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "stop_playback", lambda _reason: 0.0)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)

    jobs: queue.Queue = queue.Queue(maxsize=1)
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    _feed(mic, _wav("stop-say.wav"), jobs, VAD())
    # The four-frame "Stop." burst opens a hold but is too brief to duck.
    assert mic.tts_barge_held
    assert mic.tts_duck_restore is None
    mic.apply_whisper("tts_barge", "Stop.", None, VAD(), jobs)
    assert mic.tts_duck_restore is None

    # A sustained burst ducks in steps, stays ducked while Whisper decides,
    # and restores on release.
    jobs2: queue.Queue = queue.Queue(maxsize=1)
    mic2 = controller.MicState()
    mic2.last_manual_check = 1e12
    mic2.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    _feed(mic2, _wav("hold-on-say.wav"), jobs2, VAD())
    assert mic2.tts_duck_restore == 70
    assert current["volume"] == 20
    ramp = [int(s.rsplit(" ", 1)[1]) for s in osascript if "set volume output volume " in s and "output volume of" not in s]
    assert 20 in ramp and ramp[-1] == 20 and len(ramp) > 1  # stepped, not a single jump
    mic2.apply_whisper("tts_barge", "Hold on a second.", None, VAD(), jobs2)
    assert mic2.tts_duck_restore is None
    assert current["volume"] == 70  # verified by read-back
    assert any("set volume output volume 70" in s for s in osascript)


def test_duck_only_after_sustained_loud_frames(monkeypatch, tmp_path) -> None:
    """A two-frame flicker opens nothing and never ducks; a sustained burst does.

    The ramp is checked too: the volume moves in steps, not one hard jump.
    """
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    osascript: list[str] = []

    class _Res:
        stdout = "70"
        returncode = 0

    def fake_run(_cmd: list[str], **_kw: object) -> object:
        script = _cmd[2] if len(_cmd) > 2 else ""
        if "set volume output volume" in script:
            osascript.append(script)
        return _Res()

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)

    def _burst(frames: int) -> np.ndarray:
        return np.full(1280 * frames, 20000, dtype=np.int16)

    class _HotVad:
        def predict(self, _frame: object) -> float:
            return 0.9

    mic = controller.MicState()
    for _ in range(4):
        controller.handle_captured_frame(
            mic, _burst(1), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue(maxsize=1),
        )
    # The hold opens at the third hot frame, but four frames are not enough
    # to touch the volume.
    assert mic.tts_barge_held
    assert mic.tts_duck_restore is None
    assert not osascript

    for _ in range(6):
        controller.handle_captured_frame(
            mic, _burst(1), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue(maxsize=1),
        )
    assert mic.tts_duck_restore == 70
    volumes = [int(s.rsplit(" ", 1)[1]) for s in osascript if "set volume output volume" in s]
    assert volumes == [57, 45, 32, 20]


def test_a_stuck_duck_is_restored_by_the_watchdog(monkeypatch, tmp_path) -> None:
    """VA-PHYS-003 follow-up: a hold stuck waiting on Whisper never leaves the speaker ducked."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    osascript: list[str] = []
    volume = {"volume": 70}

    def fake_run(_cmd: list[str], **_kw: object) -> object:
        osascript.append(_cmd[2])
        return _volume_res(_cmd, volume)

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    clock = {"t": 1000.0}
    monkeypatch.setattr(controller.time, "monotonic", lambda: clock["t"])

    def _burst() -> np.ndarray:
        return np.full(1280, 20000, dtype=np.int16)

    class _HotVad:
        def predict(self, _frame: object) -> float:
            return 0.9

    mic = controller.MicState()
    mic.last_manual_check = 1e12
    for _ in range(8):
        controller.handle_captured_frame(
            mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue(maxsize=1),
        )
    assert mic.tts_duck_restore == 70
    mic.tts_barge_waiting = True
    clock["t"] += controller.DUCK_MAX_STUCK_SECONDS + 1.0
    controller.handle_captured_frame(
        mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
        0.40, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue(maxsize=1),
    )
    assert mic.tts_duck_restore is None
    assert any("set volume output volume 70" in s for s in osascript)


def test_duck_off_marker_keeps_speaker_bursts_audible(monkeypatch, tmp_path) -> None:
    """Auto probes interrupt through the same speakers, so ducking would mute
    the burst; the duck-off marker suppresses ducking for those runs only."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    osascript: list[str] = []

    class _Res:
        stdout = "70"
        returncode = 0

    def fake_run(_cmd: list[str], **_kw: object) -> object:
        osascript.append(_cmd[2])
        return _Res()

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    state = controller.MicState()
    controller.duck_output_volume(state)
    assert any("set volume output volume 20" in s for s in osascript)
    assert state.tts_duck_restore == 70
    (tmp_path / "duck-off").write_text("probe\n")
    osascript.clear()
    state2 = controller.MicState()
    controller.duck_output_volume(state2)
    assert state2.tts_duck_restore is None
    assert not osascript


def test_duck_scales_the_echo_reference(monkeypatch, tmp_path) -> None:
    """VA-BARGE-AEC: the canceller reference must match the ducked speaker.

    Measured control (real aec_audio_processing, this machine): clean speech
    against a full-gain reply reference dropped 42% rms and tiny.en heard
    "Hey Joe, you're going to jump"; the gain-matched reference kept the
    transcript perfect. duck_output_volume now records the ratio, and
    cancel_playback_echo scales the reverse stream by it.
    """
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    volume = {"volume": 70}

    class _Res:
        def __init__(self, out: str) -> None:
            self.stdout = out
            self.returncode = 0

    def fake_run(cmd: list[str], **_kw: object) -> object:
        script = cmd[2]
        if "output volume of" in script:
            return _Res(str(volume["volume"]))
        volume["volume"] = int(script.rsplit(" ", 1)[1])
        return _Res("")

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)

    mic = controller.MicState()
    controller.duck_output_volume(mic)
    assert mic.tts_duck_restore == 70
    assert abs(controller._duck_ratio - 20 / 70) < 1e-9

    samples = np.full(16000, 20000, dtype=np.int16)
    monkeypatch.setattr(controller, "_render_samples", samples)
    monkeypatch.setattr(
        controller,
        "_render_parsed",
        {"aligned": True, "started_at": controller.time.time() - 0.5, "playback_rate": 1.0},
    )
    monkeypatch.setattr(controller, "playback_echo_canceller", lambda _key: object())
    reverses: list[np.ndarray] = []

    def spy(_proc: object, frame: np.ndarray, reverse: np.ndarray) -> np.ndarray:
        reverses.append(reverse.copy())
        return frame

    monkeypatch.setattr(controller, "process_echo_block", spy)
    frame = np.full(1280, 5000, dtype=np.int16)
    when = controller.time.time()
    block = controller.render_block_at(
        samples,
        controller._render_parsed["started_at"],
        when,
        len(frame),
        controller._render_parsed["playback_rate"],
        controller.paused_playback_seconds(when),
    )
    assert block.any()
    controller.cancel_playback_echo(frame, when)  # ducked: reference scaled to the speaker
    assert np.array_equal(reverses[-1], np.rint(block * (20 / 70)).astype(np.int16))

    controller.restore_output_volume(mic)
    assert controller._duck_ratio == 1.0
    controller.cancel_playback_echo(frame, when)
    assert np.array_equal(reverses[-1], block)
    assert volume["volume"] == 70


def test_floor_freezes_while_ducked(monkeypatch, tmp_path) -> None:
    """The floor that sets the hold gate must not collapse from duck-quiet bleed.

    Floor collapse was measured live: 12 of 131 holds opened with floor 0.0,
    pinning the gate at its 320 minimum and inviting hold flicker when the
    volume came back. Quiet frames during a duck episode never enter the floor.
    """
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "stop_playback", lambda _reason: 0.0)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    volume = {"volume": 70}

    class _Res:
        def __init__(self, out: str) -> None:
            self.stdout = out
            self.returncode = 0

    def fake_run(cmd: list[str], **_kw: object) -> object:
        script = cmd[2]
        if "output volume of" in script:
            return _Res(str(volume["volume"]))
        volume["volume"] = int(script.rsplit(" ", 1)[1])
        return _Res("")

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)

    jobs: queue.Queue = queue.Queue(maxsize=1)
    vad = VAD()
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    quiet = np.zeros(1280, dtype=np.int16)
    for _ in range(5):
        controller.handle_captured_frame(
            mic, quiet, controller.time.time(), "fixture", _OwwStub(), vad,
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    assert len(mic.tts_rms_floor) == 5
    before = list(mic.tts_rms_floor)
    controller.duck_output_volume(mic)
    assert mic.tts_duck_restore == 70
    for _ in range(5):
        controller.handle_captured_frame(
            mic, quiet, controller.time.time(), "fixture", _OwwStub(), vad,
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    assert list(mic.tts_rms_floor) == before  # frozen during the duck
    controller.restore_output_volume(mic)
    controller.handle_captured_frame(
        mic, quiet, controller.time.time(), "fixture", _OwwStub(), vad,
        0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
    )
    assert len(mic.tts_rms_floor) == len(before) + 1  # learning resumes after restore


def test_cooldown_blocks_ducking_never_detection(monkeypatch, tmp_path) -> None:
    """A repeated "stop" inside the duck cooldown is still detected; only the volume change waits."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    volume = {"volume": 70}
    monkeypatch.setattr(controller.subprocess, "run", lambda cmd, **_kw: _volume_res(cmd, volume))
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    clock = {"t": 1000.0}
    monkeypatch.setattr(controller.time, "monotonic", lambda: clock["t"])

    def _burst() -> np.ndarray:
        return np.full(1280, 20000, dtype=np.int16)

    class _HotVad:
        def predict(self, _frame: object) -> float:
            return 0.9

    jobs: queue.Queue = queue.Queue(maxsize=1)
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    for _ in range(6):
        controller.handle_captured_frame(
            mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    assert mic.tts_duck_restore == 70
    for _ in range(4):
        controller.handle_captured_frame(
            mic, np.zeros(1280, dtype=np.int16), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    mic.apply_whisper("tts_barge", "The weather is nice.", None, _HotVad(), jobs)
    assert mic.tts_duck_restore is None
    assert clock["t"] < mic.tts_duck_cooldown_until  # 1.5 s duck cooldown is armed
    for _ in range(5):  # person says "stop" again immediately: detected, not re-ducked
        controller.handle_captured_frame(
            mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    assert mic.tts_barge_held
    assert mic.tts_duck_restore is None
    clock["t"] += 2.0
    controller.handle_captured_frame(
        mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
        0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
    )
    assert mic.tts_duck_restore == 70


def _volume_res(cmd: list[str], volume: dict) -> object:
    class _Res:
        pass
    script = cmd[2]
    res = _Res()
    if "output volume of" in script:
        res.stdout = str(volume["volume"])
    else:
        res.stdout = ""
        volume["volume"] = int(script.rsplit(" ", 1)[1])
    res.returncode = 0
    return res


def test_a_squashing_canceller_cannot_erase_the_stop(monkeypatch) -> None:
    """VA-INT-AUTO-040: the warm-up fit ate the interruption before the gate saw it.

    Fixture-pipeline probe: stop frames entered the canceller at rms 4130 and
    left at rms 3 with the reference playing unrelated speech, so the hot gate
    never opened and the clip was never cut. The guard returns the raw block
    whenever the filter removes energy the render reference cannot explain.
    """
    pauses: list[str] = []
    stops: list[str] = []
    resumes = 0

    monkeypatch.setattr(controller, "pause_tts_clips", lambda: pauses.append("pause"))
    monkeypatch.setattr(controller, "stop_playback", lambda reason: stops.append(reason))
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "refresh_render_reference", lambda: None)
    for name in ("silence_speech", "kill_tts_clips", "handy_start_recording", "dispatch_transcript", "play_cue", "write_status"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "resume_tts_clips", resume)

    # The clip afplay is playing, as the render reference sees it.
    reference = np.tile(_wav("hey-jarvis-say.wav"), 8)
    monkeypatch.setattr(controller, "_render_samples", reference)
    monkeypatch.setattr(
        controller,
        "_render_parsed",
        {"aligned": True, "started_at": controller.time.time() - 5.0, "playback_rate": 1.0},
    )

    def _bad_fit(_processor: object, mic: np.ndarray, _reverse: np.ndarray) -> np.ndarray:
        return (mic // 1000).astype(np.int16)

    monkeypatch.setattr(controller, "process_echo_block", _bad_fit)
    monkeypatch.setattr(controller, "playback_echo_canceller", lambda _key: object())

    vad = VAD()
    jobs: queue.Queue = queue.Queue(maxsize=1)
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    _feed(mic, np.tile(_wav("stop-say.wav"), 2), jobs, vad)
    assert pauses == []
    assert mic.tts_barge_waiting is True
    job = jobs.get_nowait()
    assert float(np.max(np.abs(job["audio"]))) > 0.2
    mic.apply_whisper("tts_barge", "Stop.", None, vad, jobs)
    assert len(stops) == 1
    assert "Stop." in stops[0]
    assert resumes == 0


def _fake_volume(volume: dict, fail_reads: list[int], fail_writes: list[int]):
    def fake_run(cmd: list[str], **_kw: object) -> object:
        class _Res:
            pass

        script = cmd[2]
        res = _Res()
        res.returncode = 0
        if "output volume of" in script:
            if fail_reads[0] > 0:
                fail_reads[0] -= 1
                res.stdout = ""  # output_volume() -> None
            else:
                res.stdout = str(volume["volume"])
        else:
            res.stdout = ""
            if fail_writes[0] > 0:
                fail_writes[0] -= 1
            else:
                volume["volume"] = int(script.rsplit(" ", 1)[1])
        return res

    return fake_run


def test_failed_restore_stays_pending_and_retries(monkeypatch, tmp_path) -> None:
    """§7: a restore attempt is not a restore. The transaction stays pending."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    volume = {"volume": 20}
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[0], fail_writes=[10])
    )

    mic = controller.MicState()
    mic.tts_duck_restore = 70
    mic.tts_duck_target = 20
    mic.tts_duck_state = "ducked"

    ok = controller.restore_output_volume(mic, now=100.0)
    assert ok is False
    assert mic.tts_duck_state == "restore_pending"
    assert mic.tts_duck_restore == 70  # state NOT cleared merely because an attempt ran
    assert (tmp_path / "duck-state.json").exists()

    # Bounded backoff: an immediate retry is gated, no osascript traffic.
    assert controller.restore_output_volume(mic, now=101.0) is False
    assert volume["volume"] == 20

    # After the backoff the pending restore completes, write succeeding,
    # and is verified by read-back.
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[0], fail_writes=[0])
    )
    assert controller.restore_output_volume(mic, now=103.0) is True
    assert volume["volume"] == 70
    assert mic.tts_duck_state == "normal"
    assert mic.tts_duck_restore is None
    assert not (tmp_path / "duck-state.json").exists()


def test_failed_probe_read_defers_restore_not_blind_write(monkeypatch, tmp_path) -> None:
    """A volume probe failure never blindly writes; the transaction stays pending."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    volume = {"volume": 20}
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[2], fail_writes=[0])
    )
    mic = controller.MicState()
    mic.tts_duck_restore = 70
    mic.tts_duck_target = 20
    assert controller.restore_output_volume(mic, now=50.0) is False
    assert mic.tts_duck_state == "restore_pending"
    assert mic.tts_duck_retry_at == 52.0  # base backoff
    assert volume["volume"] == 20  # nothing written while the probe was failing
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[0], fail_writes=[0])
    )
    assert controller.restore_output_volume(mic, now=53.0) is True
    assert volume["volume"] == 70


def test_user_volume_change_is_not_overwritten(monkeypatch, tmp_path) -> None:
    """§7: if someone changed the volume during the duck, keep their setting."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    volume = {"volume": 70}
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[0], fail_writes=[0])
    )
    mic = controller.MicState()
    controller.duck_output_volume(mic)
    assert volume["volume"] == 20
    volume["volume"] = 45  # user adjusts mid-duck
    assert controller.restore_output_volume(mic, now=10.0) is True
    assert volume["volume"] == 45
    assert mic.tts_duck_state == "normal"
    assert mic.tts_duck_restore is None
    assert abs(controller._duck_ratio - 45 / 70) < 1e-9  # reference matches the physical speaker


def test_restart_reconciles_an_outstanding_duck(monkeypatch, tmp_path) -> None:
    """§7.10: a controller that died mid-duck leaves a transaction; the next start fixes it."""
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    (tmp_path / "duck-state.json").write_text(
        json.dumps({"original": 70, "target": 20, "state": "ducked"})
    )
    volume = {"volume": 20}
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[0], fail_writes=[0])
    )
    controller.reconcile_duck_state()
    assert volume["volume"] == 70
    assert not (tmp_path / "duck-state.json").exists()


def test_restart_keeps_transaction_when_probe_fails(monkeypatch, tmp_path) -> None:
    """The startup reconcile must not delete evidence it could not verify."""
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    (tmp_path / "duck-state.json").write_text(
        json.dumps({"original": 70, "target": 20, "state": "ducked"})
    )
    volume = {"volume": 20}
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[1], fail_writes=[0])
    )
    controller.reconcile_duck_state()
    assert (tmp_path / "duck-state.json").exists()
    assert volume["volume"] == 20


def test_repeated_interruption_cycles_stay_stable(monkeypatch, tmp_path) -> None:
    """§11: three duck/restore cycles end with verified original volume every time."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    volume = {"volume": 70}
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[0], fail_writes=[0])
    )
    mic = controller.MicState()
    for _ in range(3):
        controller.duck_output_volume(mic)
        assert volume["volume"] == 20
        assert controller._duck_ratio == 20 / 70
        assert controller.restore_output_volume(mic, now=float("inf")) is True
        assert volume["volume"] == 70
        assert controller._duck_ratio == 1.0
    assert mic.tts_duck_state == "normal"
    assert not (tmp_path / "duck-state.json").exists()


class _QuietVad:
    def predict(self, _frame: object) -> float:
        return 0.1


class _SpeechVad:
    def predict(self, _frame: object) -> float:
        return 0.8


def test_ambient_estimate_tracks_rising_then_falling_noise() -> None:
    """§2A/§11: the ambient estimator follows gradual room changes both ways."""
    mic = controller.MicState()
    for level in (60, 90, 140, 200, 300, 400):
        for _ in range(20):
            mic.update_acoustic_estimates(float(level), 0.1)
    assert 340 <= mic.ambient_short <= 400
    assert 150 <= mic.ambient_long <= 400  # slow EMA trails the fast one
    for level in (300, 200, 140, 90, 60):
        for _ in range(20):
            mic.update_acoustic_estimates(float(level), 0.1)
    assert 50 <= mic.ambient_short <= 90
    assert mic.ambient_long > mic.ambient_short  # long estimate is still coming down
    assert mic.acoustic_fields()["ambient_confidence"] > 0.0


def test_ambient_estimate_rejects_transients_and_speech(monkeypatch) -> None:
    """§2A: a door slam or a spoken sentence must not raise the room baseline."""
    mic = controller.MicState()
    for _ in range(10):
        mic.update_acoustic_estimates(60.0, 0.1)
    baseline = mic.ambient_short
    mic.update_acoustic_estimates(1762.0, 0.1)  # transient spike, 4x guard
    mic.update_acoustic_estimates(2500.0, 0.8)  # human speech
    assert mic.ambient_short == baseline
    assert mic.echo_full_gain == 0.0


def test_echo_estimate_survives_ducking_without_collapsing() -> None:
    """§2B: bleed measured during a duck is re-normalized to full gain.

    Same physical relationship as the live measurement (idle ambient ~90 rms,
    speaker bleed ~175 rms): at 20% volume the mic hears ambient + 0.286*echo,
    and the echo estimate still reads the full-gain bleed.
    """
    mic = controller.MicState()
    mic.tts_active = True
    mic.ambient_short = mic.ambient_long = 90.0
    for _ in range(12):
        mic.update_acoustic_estimates(175.0, 0.1)
    assert 60 <= mic.echo_full_gain <= 110
    echo = mic.echo_full_gain
    controller._duck_ratio = 0.286
    for _ in range(12):
        mic.update_acoustic_estimates(90.0 + echo * 0.286, 0.1)
    assert abs(mic.echo_full_gain - echo) / echo < 0.25  # did not collapse
    mic.update_acoustic_estimates(3000.0, 0.8)  # human burst
    assert mic.near_end_last > 2500  # attributed to the person, not the floors
    controller._duck_ratio = 1.0


def test_ambient_dominated_room_ducks_shallower(monkeypatch, tmp_path) -> None:
    """§3: when room noise, not bleed, limits the mic, duck only halfway."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)
    volume = {"volume": 70}
    monkeypatch.setattr(
        controller.subprocess, "run", _fake_volume(volume, fail_reads=[0], fail_writes=[0])
    )
    mic = controller.MicState()
    mic.tts_active = True
    mic.ambient_short = 400.0
    mic.echo_full_gain = 175.0  # bleed is quieter than the room
    controller.duck_output_volume(mic)
    assert volume["volume"] == 45  # (70+20)//2, not the 20 anchor
    assert mic.tts_duck_restore == 70
    assert controller._duck_ratio == 45 / 70
    assert controller.restore_output_volume(mic, now=float("inf")) is True
    assert volume["volume"] == 70

    mic2 = controller.MicState()
    mic2.tts_active = True
    mic2.ambient_short = 90.0
    mic2.echo_full_gain = 400.0  # bleed dominates: full anchor duck
    controller.duck_output_volume(mic2)
    assert volume["volume"] == 20
    assert controller._duck_ratio == 20 / 70
    assert controller.restore_output_volume(mic2, now=float("inf")) is True
    assert volume["volume"] == 70


def test_rising_ambient_noise_alone_neither_holds_nor_ducks(monkeypatch, tmp_path) -> None:
    """§11: environmental noise ramping to 400 rms opens nothing and ducks nothing.

    The gate rides on the floor, which follows the noise; VAD stays quiet, so
    no hold opens and the volume is never touched.
    """
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    volume = {"volume": 70}
    writes: list[str] = []

    def fake_run(cmd: list[str], **_kw: object) -> object:
        if "set volume" in cmd[2]:
            writes.append(cmd[2])
        return _volume_res(cmd, volume)

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    jobs: queue.Queue = queue.Queue(maxsize=1)
    for level in (100, 150, 200, 250, 300, 350, 400):
        frame = np.full(1280, level, dtype=np.int16)
        controller.handle_captured_frame(
            mic, frame, controller.time.time(), "fixture", _OwwStub(), _QuietVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    assert not mic.tts_barge_held
    assert mic.tts_duck_restore is None
    assert not writes
    # The first pre-playback frame seeds ambient; playback noise never feeds it
    # (spec §2A protection), it is attributed to the echo path instead.
    assert mic.ambient_short <= 100.0
    assert mic.echo_full_gain > 150
    assert volume["volume"] == 70


def test_partial_recognition_kicks_before_the_clip_flushes(monkeypatch) -> None:
    """Spec §8: eight frames of confirmed voice start Whisper while capture continues.

    The 16-frame flush contract is untouched — the full clip still gets its
    own decision; the partial only buys an early stop.
    """
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "stop_playback", lambda reason: (_ for _ in ()).throw(AssertionError("stop_playback")))
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    for name in ("silence_speech", "kill_tts_clips", "handy_start_recording", "dispatch_transcript", "play_cue", "write_status"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    mic = controller.MicState()
    mic.last_manual_check = 1e12
    mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    jobs: queue.Queue = queue.Queue(maxsize=1)
    _feed(mic, _wav("hold-on-say.wav"), jobs, VAD())
    assert mic.whisper_pending is not None
    assert mic.whisper_pending["kind"] == "tts_barge_partial"
    assert mic.tts_barge_partial_kicked is True
    assert mic.tts_barge_next is not None  # the full clip waits for its own pass


def test_partial_stop_halts_without_the_full_clip(monkeypatch, tmp_path) -> None:
    """A verbatim stop in the partial clip stops playback immediately (§8 target)."""
    stops: list[str] = []
    monkeypatch.setenv("OMP_VOICE_BARGE_TRACE", "1")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    monkeypatch.setattr(
        controller,
        "stop_playback",
        lambda reason: (stops.append(reason), controller.time.monotonic())[1],
    )
    monkeypatch.setattr(controller, "restore_output_volume", lambda _mic: True)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)

    now = controller.time.monotonic()
    mic = controller.MicState()
    mic.state = "IDLE"
    mic.tts_barge_held = True
    mic.tts_barge_voice = True
    mic.barge_onset_mono = now - 0.4
    mic.barge_stages = {"gate": now - 0.6, "hold": now - 0.4, "duck": now - 0.25, "capture": now - 0.4, "partial": now - 0.1}
    jobs: queue.Queue = queue.Queue(maxsize=1)
    assert mic.apply_whisper("tts_barge_partial", "Hey Jarvis stop", None, None, jobs) is True
    assert len(stops) == 1
    assert "partial" in stops[0]
    assert mic.tts_barge_held is False
    assert mic.tts_barge_waiting is False
    assert mic.barge_stages == {}
    events = [json.loads(line) for line in (tmp_path / "barge-trace.jsonl").read_text().splitlines()]
    latency = next(e for e in events if e["stage"] == "latency")
    assert latency["gate_to_stop_s"] > 0
    assert latency["partial_to_decision_s"] >= 0


def test_partial_non_stop_keeps_the_hold_and_queues_the_full_clip(monkeypatch) -> None:
    """A partial that is not a stop is not a decision: the hold stays, the full
    clip gets its Whisper pass, and the speaker is never restored early."""
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    mic = controller.MicState()
    mic.state = "IDLE"
    mic.tts_barge_held = True
    mic.tts_barge_voice = True
    mic.tts_barge_next = (np.zeros(16, dtype=np.float32), "Hey Jarvis. stop.")
    jobs: queue.Queue = queue.Queue(maxsize=1)
    assert mic.apply_whisper("tts_barge_partial", "hello there", None, None, jobs) is True
    assert mic.tts_barge_held is True
    assert mic.tts_barge_next is None
    assert mic.whisper_pending is not None
    assert mic.whisper_pending["kind"] == "tts_barge"
