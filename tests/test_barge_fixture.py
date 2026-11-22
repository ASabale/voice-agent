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
    calls = _master_writes(monkeypatch)
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "stop_playback", lambda _reason: 0.0)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller.time, "sleep", lambda _s: None)

    jobs: queue.Queue = queue.Queue(maxsize=1)
    mic = controller.MicState()
    mic.last_manual_check = 1e12
    mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    _feed(mic, _wav("stop-say.wav"), jobs, VAD())
    # The four-frame "Stop." burst opens a hold but is too brief to duck.
    assert mic.tts_barge_held
    assert mic.tts_stream_gain is None
    mic.apply_whisper("tts_barge", "Stop.", None, VAD(), jobs)
    assert mic.tts_stream_gain is None

    # A sustained burst ducks the reply stream, stays ducked while Whisper
    # decides, and restores on release. The master volume is never touched.
    jobs2: queue.Queue = queue.Queue(maxsize=1)
    mic2 = controller.MicState()
    mic2.last_manual_check = 1e12
    mic2.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter"))  # type: ignore[method-assign]
    _feed(mic2, _wav("hold-on-say.wav"), jobs2, VAD())
    assert mic2.tts_stream_gain is not None
    assert _gain(tmp_path) < 1.0
    mic2.apply_whisper("tts_barge", "Hold on a second.", None, VAD(), jobs2)
    assert mic2.tts_stream_gain is None
    assert _gain(tmp_path) == 1.0
    assert not any("volume" in c for c in calls)


def test_duck_only_after_sustained_loud_frames(monkeypatch, tmp_path) -> None:
    """A two-frame flicker opens nothing and never ducks; a sustained burst does.

    The duck lowers only the VoiceBox stream gain, never the master volume.
    """
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    calls = _master_writes(monkeypatch)
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
    assert mic.tts_stream_gain is None
    assert not (tmp_path / "stream-gain.json").exists()

    for _ in range(6):
        controller.handle_captured_frame(
            mic, _burst(1), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue(maxsize=1),
        )
    assert mic.tts_stream_gain is not None
    assert _gain(tmp_path) == mic.tts_stream_gain < 1.0
    assert not any("volume" in c for c in calls)


def test_a_stuck_duck_is_restored_by_the_watchdog(monkeypatch, tmp_path) -> None:
    """VA-PHYS-003 follow-up: a hold stuck waiting on Whisper never leaves the reply ducked."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    _master_writes(monkeypatch)
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
    assert mic.tts_stream_gain is not None
    mic.tts_barge_waiting = True
    clock["t"] += controller.DUCK_MAX_STUCK_SECONDS + 1.0
    controller.handle_captured_frame(
        mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
        0.40, "hey_jarvis", 0.5, 5.0, 15.0, queue.Queue(maxsize=1),
    )
    assert mic.tts_stream_gain is None
    assert _gain(tmp_path) == 1.0


def test_duck_off_marker_keeps_speaker_bursts_audible(monkeypatch, tmp_path) -> None:
    """Auto probes interrupt through the same speakers, so ducking would mute
    the burst; the duck-off marker suppresses ducking for those runs only."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    state = controller.MicState()
    controller.duck_output_volume(state)
    assert _gain(tmp_path) == 0.2
    controller.restore_output_volume(state)
    (tmp_path / "duck-off").write_text("probe\n")
    state2 = controller.MicState()
    controller.duck_output_volume(state2)
    assert state2.tts_stream_gain is None
    assert _gain(tmp_path) == 1.0


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
    mic = controller.MicState()
    controller.duck_output_volume(mic)
    assert controller._duck_ratio == 0.2

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
    assert np.array_equal(reverses[-1], np.rint(block * 0.2).astype(np.int16))

    controller.restore_output_volume(mic)
    assert controller._duck_ratio == 1.0
    controller.cancel_playback_echo(frame, when)
    assert np.array_equal(reverses[-1], block)


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
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    _master_writes(monkeypatch)

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
    assert mic.tts_stream_gain is not None
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
    _master_writes(monkeypatch)
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
    assert mic.tts_stream_gain is not None
    for _ in range(4):
        controller.handle_captured_frame(
            mic, np.zeros(1280, dtype=np.int16), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    mic.apply_whisper("tts_barge", "The weather is nice.", None, _HotVad(), jobs)
    assert mic.tts_stream_gain is None
    assert clock["t"] < mic.tts_duck_cooldown_until  # 1.5 s duck cooldown is armed
    for _ in range(5):  # person says "stop" again immediately: detected, not re-ducked
        controller.handle_captured_frame(
            mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
            0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
        )
    assert mic.tts_barge_held
    assert mic.tts_stream_gain is None
    clock["t"] += 2.0
    controller.handle_captured_frame(
        mic, _burst(), controller.time.time(), "fixture", _OwwStub(), _HotVad(),
        0.40, "hey_jarvis", 0.5, 5.0, 15.0, jobs,
    )
    assert mic.tts_stream_gain is not None




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


def _master_writes(monkeypatch) -> list[str]:
    """Record any osascript call; ducking must never produce one."""
    calls: list[str] = []

    def fake_run(cmd: list[str], **_kw: object) -> object:
        calls.append(" ".join(cmd))

        class _Res:
            stdout = ""
            returncode = 0

        return _Res()

    monkeypatch.setattr(controller.subprocess, "run", fake_run)
    return calls


def _gain(tmp_path) -> float:
    return json.loads((tmp_path / "stream-gain.json").read_text())["gain"]


def test_failed_restore_stays_pending_and_retries(monkeypatch, tmp_path) -> None:
    """§7: a restore attempt is not a restore. The transaction stays pending."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    mic = controller.MicState()
    controller.duck_output_volume(mic)
    monkeypatch.setattr(controller, "write_stream_gain", lambda _g: False)
    assert controller.restore_output_volume(mic, now=100.0) is False
    assert mic.tts_duck_state == "restore_pending"
    assert mic.tts_stream_gain == 0.2  # state NOT cleared merely because an attempt ran
    assert (tmp_path / "duck-state.json").exists()
    monkeypatch.undo()
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    assert controller.restore_output_volume(mic, now=101.0) is False  # backoff gate
    assert _gain(tmp_path) == 0.2
    assert controller.restore_output_volume(mic, now=103.0) is True
    assert _gain(tmp_path) == 1.0
    assert mic.tts_duck_state == "normal"
    assert not (tmp_path / "duck-state.json").exists()






def test_repeated_interruption_cycles_stay_stable(monkeypatch, tmp_path) -> None:
    """§11: three duck/restore cycles end at full gain every time."""
    monkeypatch.setenv("OMP_VOICE_DUCK_VOLUME", "20")
    monkeypatch.setattr(controller, "STATE_DIR", tmp_path)
    mic = controller.MicState()
    for _ in range(3):
        controller.duck_output_volume(mic)
        assert _gain(tmp_path) == 0.2
        assert controller._duck_ratio == 0.2
        assert controller.restore_output_volume(mic, now=float("inf")) is True
        assert _gain(tmp_path) == 1.0
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


def test_a_stale_reference_is_not_attributed_to_the_speaker(monkeypatch) -> None:
    """§2B: bleed attribution needs the render reference this frame.

    The estimator reads the canceller's per-frame signals. A render reference
    that has gone away leaves those signals behind, and the estimator then
    explains every frame as "unmeasured bleed" instead of learning the coupling
    gain: the echo estimate stays at 0 and the barge gate loses its floor.
    """
    reference = np.full(16000, 20000, dtype=np.int16)
    monkeypatch.setattr(controller, "_render_samples", reference)
    monkeypatch.setattr(
        controller,
        "_render_parsed",
        {"aligned": True, "started_at": controller.time.time() - 1.0, "playback_rate": 1.0},
    )
    monkeypatch.setattr(controller, "playback_echo_canceller", lambda _key: object())
    monkeypatch.setattr(controller, "process_echo_block", lambda _proc, frame, _reverse: frame)
    controller.cancel_playback_echo(np.full(1280, 18000, dtype=np.int16), controller.time.time())
    assert controller._last_ref_rms >= controller.ECHO_REF_ACTIVE_RMS  # the signal exists

    monkeypatch.undo()  # the clip ended: no render reference, stale signal left behind

    mic = controller.MicState()
    mic.tts_active = True
    mic.ambient_short = mic.ambient_long = 90.0
    for _ in range(12):
        mic.update_acoustic_estimates(175.0, 0.1)
    assert 60 <= mic.echo_full_gain <= 110  # the bleed is still measurable


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
    calls = _master_writes(monkeypatch)
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
    assert mic.tts_stream_gain is None
    assert not calls
    # The first pre-playback frame seeds ambient; playback noise never feeds it
    # (spec §2A protection), it is attributed to the echo path instead.
    assert mic.ambient_short <= 100.0
    assert mic.echo_full_gain > 150


def test_partial_recognition_kicks_before_the_clip_flushes(monkeypatch) -> None:
    """Spec §8: eight frames of confirmed voice start Whisper while capture continues.

    The 16-frame flush contract is untouched — the full clip still gets its
    own decision; the partial only buys an early stop.
    """
    monkeypatch.setattr(controller, "pause_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: None)
    monkeypatch.setattr(controller, "stop_playback", lambda reason: (_ for _ in ()).throw(AssertionError("stop_playback")))
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: True)
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


def test_dictation_frames_are_attributed_to_bleed_or_person() -> None:
    """§2C: frames at the expected bleed level never count as human speech.

    The live "Thank you." spam came from Whisper tiny transcribing pure bleed
    and room noise; the chunk gate counts attribution frames instead of
    trusting the transcript text.
    """
    mic = controller.MicState()
    mic.tts_active = True
    mic.ambient_short = mic.ambient_long = 90.0
    mic.echo_full_gain = 175.0
    controller._duck_ratio = 1.0
    for _ in range(10):
        mic.count_dictation_frame(175.0, 0.9)   # bleed exactly at the expectation
        mic.count_dictation_frame(1600.0, 0.1)  # loud noise with no VAD support
    for _ in range(5):
        mic.count_dictation_frame(3000.0, 0.8)  # the person riding over the bleed
    assert mic.dict_echo_frames == 10
    assert mic.dict_human_frames == 5
    controller._duck_ratio = 0.286
    mic.count_dictation_frame(90.0 + 175.0 * 0.286, 0.9)  # ducked bleed is still bleed
    assert mic.dict_human_frames == 5
    controller._duck_ratio = 1.0
    idle = controller.MicState()
    for _ in range(10):
        idle.count_dictation_frame(1600.0, 0.12)  # no-TTS room noise
    assert idle.dict_human_frames == 0


