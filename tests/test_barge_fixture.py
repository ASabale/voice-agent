"""A short stop is paused, then Whisper hears it, before playback is allowed to resume.

The thresholds are unchanged. The stop fixture's third hot frame is the last
loud frame, so the old path resumed before recognition.
"""

import importlib.machinery
import importlib.util
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
        stdout = "70"
        returncode = 0

    def fake_run(_cmd: list[str], **_kw: object) -> object:
        script = _cmd[2]
        osascript.append(script)
        if "output volume of" in script:
            return _Res()
        current["volume"] = int(script.rsplit(" ", 1)[1])
        return _Res()

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
    ramp = [int(s.rsplit(" ", 1)[1]) for s in osascript if "set volume output volume " in s and "output volume of" not in s]
    assert 20 in ramp and ramp[-1] == 20 and len(ramp) > 1  # stepped, not a single jump
    mic2.apply_whisper("tts_barge", "Hold on a second.", None, VAD(), jobs2)
    assert mic2.tts_duck_restore is None
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

    class _Res:
        stdout = "70"
        returncode = 0

    def fake_run(_cmd: list[str], **_kw: object) -> object:
        osascript.append(_cmd[2])
        return _Res()

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
