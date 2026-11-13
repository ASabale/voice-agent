"""Wake phrase and clip-gain seams. Grammar is the source of wakes; gain cap is an argument."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PATH = _ROOT / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_structure", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")

_GRAMMAR = controller.load_command_grammar(_ROOT / "grammar.json")


@pytest.mark.parametrize(
    "phrase",
    [
        "hey jarvis",
        "Hey Jarvis",
        "hey, jarvis",
        "ok jarvis",
        "hello jarvis!",
        "Jarvis",
        "jarvis?",
        "jarvis.",
    ],
)
def test_wake_phrase_accepts_grammar_wakes_and_trailing_punctuation(phrase: str) -> None:
    assert controller.is_wake_phrase(phrase, grammar=_GRAMMAR)


@pytest.mark.parametrize(
    "phrase",
    [
        "heyjarvis",
        " jarvis",
        "hey jarvis please",
        "good morning jarvis",
        "stop",
        "jarvis;",
        "hey. jarvis",
    ],
)
def test_wake_phrase_rejects_non_wakes(phrase: str) -> None:
    assert not controller.is_wake_phrase(phrase, grammar=_GRAMMAR)


def test_clip_for_whisper_uses_the_passed_cap() -> None:
    audio = np.array([0.05, -0.05], dtype=np.float32)
    # peak 0.05 -> 0.5/peak = 10, so the cap is the binding limit
    gained = controller.clip_for_whisper(audio, 6.0)
    assert gained.tolist() == pytest.approx([0.3, -0.3])
    softer = controller.clip_for_whisper(audio, 5.0)
    assert softer.tolist() == pytest.approx([0.25, -0.25])


def test_clip_for_whisper_leaves_near_silence() -> None:
    audio = np.array([0.001, -0.001], dtype=np.float32)
    gained = controller.clip_for_whisper(audio, 6.0)
    assert gained.tolist() == pytest.approx(audio.tolist())


def _pcm16(path: Path) -> np.ndarray:
    import wave

    with wave.open(str(path)) as handle:
        assert (handle.getframerate(), handle.getnchannels(), handle.getsampwidth()) == (16000, 1, 2)
        return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)


def _peak_wake(samples: np.ndarray) -> float:
    from openwakeword.model import Model

    model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    peak = 0.0
    for start in range(0, len(samples) - 1279, 1280):
        pred = model.predict(samples[start : start + 1280])
        if pred:
            peak = max(peak, float(max(pred.values())))
    return peak


def test_hey_jarvis_file_scores_above_the_controller_threshold_without_the_mic() -> None:
    # macOS `say` rendered these files. Do not play them: the live controller owns the MacBook mic.
    hey = _peak_wake(_pcm16(_ROOT / "tests" / "fixtures" / "hey-jarvis-say.wav"))
    other = _peak_wake(_pcm16(_ROOT / "tests" / "fixtures" / "good-morning-say.wav"))
    assert hey >= 0.5
    assert other < 0.5


def test_whisper_verifier_accepts_the_wake_file_and_rejects_the_other() -> None:
    # Same prompt and gain as handle_idle_frame. Do not call enter_dictating:
    # that runs silence_speech and starts Handy on the live mic.
    from faster_whisper import WhisperModel

    whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    prompt = "Hey Jarvis, Jarvis, send prompt, prompt this, submit prompt, scratch that, undo that, clear draft."
    heard: dict[str, str] = {}
    for name in ("hey-jarvis-say.wav", "good-morning-say.wav"):
        samples = _pcm16(_ROOT / "tests" / "fixtures" / name)
        audio = controller.clip_for_whisper(samples.astype(np.float32) / 32768.0, 6.0)
        segments, _info = whisper.transcribe(
            audio, language="en", beam_size=1, without_timestamps=True, initial_prompt=prompt
        )
        heard[name] = " ".join(segment.text for segment in segments).strip()
    assert controller.is_wake_phrase(heard["hey-jarvis-say.wav"], grammar=_GRAMMAR)
    assert not controller.is_wake_phrase(heard["good-morning-say.wav"], grammar=_GRAMMAR)


def test_barge_clips_classify_without_stopping_playback() -> None:
    # The TTS barge prompt. Do not call stop_playback: it runs silence_speech.
    from faster_whisper import WhisperModel

    whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    prompt = "Hey Jarvis. stop."
    classified: dict[str, bool] = {}
    tokens: dict[str, list[str]] = {}
    for name in ("stop-say.wav", "hold-on-say.wav", "sentence-stop-say.wav"):
        samples = _pcm16(_ROOT / "tests" / "fixtures" / name)
        audio = controller.clip_for_whisper(samples.astype(np.float32) / 32768.0, 6.0)
        segments, _info = whisper.transcribe(
            audio, language="en", beam_size=1, without_timestamps=True, initial_prompt=prompt
        )
        text = " ".join(segment.text for segment in segments).strip()
        tokens[name] = controller._command_tokens(text)
        classified[name] = controller._is_playback_barge(tokens[name])
    assert classified["stop-say.wav"] is True
    assert tokens["stop-say.wav"] == ["stop"]
    assert classified["hold-on-say.wav"] is True
    assert tokens["hold-on-say.wav"] == ["hold", "on", "a", "second"]
    assert classified["sentence-stop-say.wav"] is False
    assert "stop" in tokens["sentence-stop-say.wav"]
    assert len(tokens["sentence-stop-say.wav"]) > 1


def _feed_idle(mic: object, samples: np.ndarray, oww: object) -> None:
    import queue

    now = 10.0
    for start in range(0, len(samples) - 1279, 1280):
        frame = samples[start : start + 1280]
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        mic.handle_idle_frame(frame, now, rms, 0.0, False, "test", oww, None, "hey_jarvis", 0.5, queue.Queue())
        now += 0.08
        if mic.state == "DICTATING":
            return


def test_idle_frame_takes_the_wake_file_without_starting_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    # The real enter_dictating calls silence_speech and handy_start_recording.
    forbidden: list[str] = []

    def boom(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            forbidden.append(name)
            raise AssertionError(name)

        return _blocked

    for name in (
        "silence_speech",
        "kill_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "play_cue",
        "dispatch_transcript",
        "pause_tts_clips",
        "resume_tts_clips",
        "apply_handy_model",
        "apply_voicebox_model",
        "stop_playback",
    ):
        monkeypatch.setattr(controller, name, boom(name))
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)

    from openwakeword.model import Model

    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    reasons: list[str] = []

    def run(name: str) -> controller.MicState:
        mic = controller.MicState()
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12

        def fake_enter(reason: str, _oww: object, _vad: object) -> None:
            reasons.append(reason)
            mic.state = "DICTATING"

        mic.enter_dictating = fake_enter  # type: ignore[method-assign]
        _feed_idle(mic, _pcm16(_ROOT / "tests" / "fixtures" / name), oww)
        oww.reset()
        return mic

    wake = run("hey-jarvis-say.wav")
    other = run("good-morning-say.wav")
    assert wake.state == "DICTATING"
    assert len(reasons) == 1
    assert reasons[0].startswith("openWakeWord score=")
    assert float(reasons[0].rsplit("=", 1)[1]) >= 0.5
    assert other.state == "IDLE"
    assert forbidden == []


def test_a_dismissed_handy_blocks_the_wake_file_until_the_window_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    # score_wake_blocked_until is 45 s after Handy is closed. The real enter_dictating starts Handy.
    reasons: list[str] = []

    def boom(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(name)

        return _blocked

    for name in (
        "silence_speech",
        "kill_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "play_cue",
        "dispatch_transcript",
        "pause_tts_clips",
        "resume_tts_clips",
        "stop_playback",
        "write_status",
    ):
        monkeypatch.setattr(controller, name, boom(name))
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)

    from openwakeword.model import Model

    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    samples = _pcm16(_ROOT / "tests" / "fixtures" / "hey-jarvis-say.wav")

    def run(blocked_until: float) -> controller.MicState:
        mic = controller.MicState()
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12
        mic.score_wake_blocked_until = blocked_until

        def fake_enter(reason: str, _oww: object, _vad: object) -> None:
            reasons.append(reason)
            mic.state = "DICTATING"

        mic.enter_dictating = fake_enter  # type: ignore[method-assign]
        _feed_idle(mic, samples, oww)
        oww.reset()
        return mic

    blocked = run(1e9)
    assert blocked.state == "IDLE"
    assert reasons == []

    opened = run(0.0)
    assert opened.state == "DICTATING"
    assert len(reasons) == 1
    assert reasons[0].startswith("openWakeWord score=")
    assert float(reasons[0].rsplit("=", 1)[1]) >= 0.5


def test_tts_barge_frames_queue_whisper_without_stopping_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    # A hearing is not a stop yet. pause_tts_clips would SIGSTOP afplay. stop_playback runs silence_speech.
    calls: list[str] = []

    def record(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            calls.append(name)

        return _blocked

    def boom(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            calls.append(f"FORBIDDEN:{name}")
            raise AssertionError(name)

        return _blocked

    for name in ("pause_tts_clips", "resume_tts_clips"):
        monkeypatch.setattr(controller, name, record(name))
    for name in (
        "silence_speech",
        "kill_tts_clips",
        "stop_playback",
        "handy_start_recording",
        "handy_cancel",
        "play_cue",
        "dispatch_transcript",
        "apply_handy_model",
        "apply_voicebox_model",
    ):
        monkeypatch.setattr(controller, name, boom(name))
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)

    base = _pcm16(_ROOT / "tests" / "fixtures" / "stop-say.wav")
    loud = [
        base[start : start + 1280]
        for start in range(0, len(base) - 1279, 1280)
        if float(np.sqrt(np.mean(base[start : start + 1280].astype(np.float32) ** 2))) >= 320
    ]
    # The floor is speaker bleed. Loud frames fed first become that floor and
    # then fail the 2.4x gate. Fill it with quiet frames, then the stop frames.
    bleed = np.zeros(1280, dtype=np.int16)
    bleed[:] = 150
    frames = [bleed.copy() for _ in range(25)]
    # Three hot frames arm the hold, two are skipped, three more set the voice flag.
    frames.extend(frame.copy() for frame in (loud * 2)[:8])
    frames.extend(np.zeros(1280, dtype=np.int16) for _ in range(6))

    class _Model:
        def reset(self) -> None:
            return None

    import queue

    mic = controller.MicState()
    mic.tts_active = True
    mic.last_manual_check = 1e12
    mic.last_tts_check = 1e12
    jobs: queue.Queue = queue.Queue(maxsize=1)
    now = 10.0
    for frame in frames:
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        mic.handle_idle_frame(
            frame, now, rms, 0.9, True, "MacBook Pro Speakers", _Model(), None, "hey_jarvis", 0.5, jobs
        )
        now += 0.08
        if mic.whisper_pending is not None:
            break

    assert mic.state == "IDLE"
    assert mic.whisper_pending is not None
    assert mic.whisper_pending["kind"] == "tts_barge"
    job = jobs.get_nowait()
    assert job["prompt"] == "Hey Jarvis. stop."
    assert "pause_tts_clips" not in calls
    assert "resume_tts_clips" not in calls
    assert not any(item.startswith("FORBIDDEN:") for item in calls)

    from faster_whisper import WhisperModel

    whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    segments, _info = whisper.transcribe(
        job["audio"], language="en", beam_size=1, without_timestamps=True, initial_prompt=job["prompt"]
    )
    text = " ".join(segment.text for segment in segments).strip()
    assert controller._is_playback_barge(controller._command_tokens(text))


def test_apply_whisper_stops_a_barge_and_does_not_open_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    # stop_playback calls silence_speech. The real enter_dictating starts Handy.
    stops: list[str] = []
    monkeypatch.setattr(controller, "stop_playback", lambda reason: stops.append(reason))

    def boom(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(name)

        return _blocked

    for name in (
        "silence_speech",
        "kill_tts_clips",
        "pause_tts_clips",
        "resume_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "play_cue",
        "dispatch_transcript",
    ):
        monkeypatch.setattr(controller, name, boom(name))

    def refuse_enter(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("enter_dictating")

    def barge(heard: str) -> None:
        mic = controller.MicState()
        mic.tts_active = True
        mic.tts_barge_held = True
        mic.enter_dictating = refuse_enter  # type: ignore[method-assign]
        assert mic.apply_whisper("tts_barge", heard, None, None) is True
        assert mic.state == "IDLE"
        assert mic.tts_active is False
        assert mic.tts_barge_held is False

    barge("stop.")
    barge("Hold on a second.")
    assert stops == [
        "Heard 'stop.' over TTS -> stopping speech, not opening Handy",
        "Heard 'Hold on a second.' over TTS -> stopping speech, not opening Handy",
    ]

    sentence = controller.MicState()
    sentence.tts_active = True
    sentence.enter_dictating = refuse_enter  # type: ignore[method-assign]
    assert sentence.apply_whisper("tts_barge", "The sentence ends with stop.", None, None) is False
    assert sentence.tts_active is True
    assert len(stops) == 2

    over_tts = controller.MicState()
    over_tts.tts_active = True
    over_tts.enter_dictating = refuse_enter  # type: ignore[method-assign]
    assert over_tts.apply_whisper("tts_barge", "Hey Jarvis.", None, None) is True
    assert over_tts.state == "IDLE"
    assert over_tts.tts_active is True
    assert len(stops) == 2

    entered: list[str] = []
    verified = controller.MicState()

    def fake_enter(reason: str, _oww: object, _vad: object) -> None:
        entered.append(reason)
        verified.state = "DICTATING"

    verified.enter_dictating = fake_enter  # type: ignore[method-assign]
    assert verified.apply_whisper("idle_verify", "Hey Jarvis.", None, None) is True
    assert entered == ["whisper heard 'Hey Jarvis.'"]
    assert verified.state == "DICTATING"


def test_a_non_stop_hearing_does_not_resume_the_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    resumes: list[str] = []
    monkeypatch.setattr(controller, "resume_tts_clips", lambda: resumes.append("resume"))

    def boom(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(name)

        return _blocked

    for name in ("pause_tts_clips", "stop_playback", "silence_speech", "kill_tts_clips", "handy_start_recording"):
        monkeypatch.setattr(controller, name, boom(name))

    mic = controller.MicState()
    mic.state = "IDLE"
    mic.tts_active = True
    mic.tts_barge_held = True
    mic.tts_barge_waiting = True
    assert mic.apply_whisper("tts_barge", "Thank you.", None, None) is False
    assert resumes == []
    assert mic.tts_active is True
    assert mic.tts_barge_held is False
    assert mic.tts_barge_waiting is False


def test_idle_verify_submits_or_scratches_without_posting(monkeypatch: pytest.MonkeyPatch) -> None:
    # dispatch_transcript follows the live session. play_cue starts afplay.
    posted: list[str] = []
    cues: list[str] = []

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        if text == "send prompt":
            return {"action": "sent"}
        return {"action": "scratched"}

    def play(sound: str, wait: bool = False) -> None:
        cues.append(sound)

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "play_cue", play)

    def boom(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(name)

        return _blocked

    for name in ("silence_speech", "stop_playback", "handy_start_recording", "pause_tts_clips", "kill_tts_clips"):
        monkeypatch.setattr(controller, name, boom(name))

    def refuse_enter(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("enter_dictating")

    send = controller.MicState()
    send.enter_dictating = refuse_enter  # type: ignore[method-assign]
    assert send.apply_whisper("idle_verify", "send prompt", None, None) is False
    assert posted == ["send prompt"]
    assert cues == [controller.SOUND_SEND]
    assert send.state == "IDLE"

    synonym = controller.MicState()
    synonym.enter_dictating = refuse_enter  # type: ignore[method-assign]
    assert synonym.apply_whisper("idle_verify", "all done", None, None) is False
    assert posted == ["send prompt", "send prompt"]
    assert cues == [controller.SOUND_SEND, controller.SOUND_SEND]

    scratch = controller.MicState()
    scratch.enter_dictating = refuse_enter  # type: ignore[method-assign]
    assert scratch.apply_whisper("idle_verify", "scratch that", None, None) is False
    assert posted == ["send prompt", "send prompt", "scratch that"]
    assert cues[-1] == controller.SOUND_CANCEL
    assert scratch.state == "IDLE"

    alone = controller.MicState()
    alone.enter_dictating = refuse_enter  # type: ignore[method-assign]
    assert alone.apply_whisper("idle_verify", "stop", None, None) is False
    assert alone.apply_whisper("idle_verify", "good morning", None, None) is False
    assert posted == ["send prompt", "send prompt", "scratch that"]
    assert len(cues) == 3
    assert alone.state == "IDLE"


class _Reset:
    def reset(self) -> None:
        return None

    def reset_states(self) -> None:
        return None


def test_dictation_flush_routes_the_handy_transcript_without_touching_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    # handy_stop_recording toggles the live app. write_status replaces status.json.
    posted: list[str] = []
    cues: list[str] = []
    statuses: list[tuple[str, dict | None]] = []
    handy_starts = 0
    rows: list[tuple[int, str] | None] = []

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        matched = controller.match_command(text)
        return {"action": matched["action"] if matched else "appended"}

    def play(sound: str, wait: bool = False) -> None:
        cues.append(sound)

    def stop_handy() -> bool:
        return bool(rows)

    def wait_row(_prev: int, timeout_sec: float = 2.2) -> tuple[int, str] | None:
        return rows[0] if rows else None

    def start_handy(*_args: object, **_kwargs: object) -> bool:
        nonlocal handy_starts
        handy_starts += 1
        return True

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "play_cue", play)
    monkeypatch.setattr(controller, "handy_stop_recording", stop_handy)
    monkeypatch.setattr(controller, "wait_for_new_history_row", wait_row)
    monkeypatch.setattr(controller, "handy_start_recording", start_handy)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "write_status", lambda state, extra=None: statuses.append((state, extra)))
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)

    def boom(name: str):
        def _blocked(*_args: object, **_kwargs: object) -> None:
            raise AssertionError(name)

        return _blocked

    for name in ("silence_speech", "stop_playback", "handy_cancel", "pause_tts_clips", "kill_tts_clips", "bridge_request"):
        monkeypatch.setattr(controller, name, boom(name))

    def flush(transcript: str | None) -> controller.MicState:
        nonlocal handy_starts
        handy_starts = 0
        rows.clear()
        if transcript is not None:
            rows.append((7, transcript))
        mic = controller.MicState()
        mic.state = "DICTATING"
        mic.speech_seen_in_chunk = True
        now = 100.0
        mic.chunk_started_at = now
        mic.last_handy_ui_check = now
        mic.last_speech_at = now - 10
        mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
        mic.handle_dictating_frame(
            np.zeros(1280, dtype=np.int16), now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, __import__("queue").Queue()
        )
        return mic

    sent = flush("all done")
    assert sent.state == "IDLE"
    assert posted == ["all done"]
    assert cues == [controller.SOUND_SEND]
    assert handy_starts == 0
    assert statuses[-1][0] == "IDLE"

    scratched = flush("scratch that")
    assert scratched.state == "DICTATING"
    assert posted[-1] == "scratch that"
    assert cues[-1] == controller.SOUND_CANCEL
    assert handy_starts == 1

    stopped = flush(None)
    assert stopped.state == "IDLE"
    assert posted[-1] == "scratch that"
    assert cues[-1] == controller.SOUND_PAUSE
    assert handy_starts == 0


def test_fast_command_flushes_before_the_pause_without_touching_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1.5s of silence is the fast-command gate. The normal pause in this test is 5s.
    import queue

    posted: list[str] = []
    cues: list[str] = []
    stops = 0

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        matched = controller.match_command(text)
        return {"action": matched["action"] if matched else "appended"}

    def stop_handy() -> bool:
        nonlocal stops
        stops += 1
        return True

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(controller, "handy_stop_recording", stop_handy)
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: (7, "stop"))
    monkeypatch.setattr(controller, "handy_start_recording", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("handy_start")))
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)
    for name in ("silence_speech", "stop_playback", "handy_cancel", "pause_tts_clips", "kill_tts_clips", "bridge_request"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    flagged = controller.MicState()
    flagged.state = "DICTATING"
    assert flagged.apply_whisper("fast_cmd", "stop", None, None) is False
    assert flagged.pending_fast_flush is True
    assert flagged.state == "DICTATING"
    assert posted == []

    quiet = controller.MicState()
    quiet.state = "DICTATING"
    assert quiet.apply_whisper("fast_cmd", "good morning", None, None) is False
    assert quiet.pending_fast_flush is False

    now = 100.0
    frame = np.zeros(1280, dtype=np.int16)
    flagged.speech_seen_in_chunk = True
    flagged.chunk_started_at = now
    flagged.last_handy_ui_check = now
    flagged.last_speech_at = now - 1.6
    flagged.dict_speech_frames = [frame.copy()]
    flagged.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue())
    assert flagged.state == "IDLE"
    assert flagged.pending_fast_flush is False
    assert posted == ["stop"]
    assert cues == [controller.SOUND_PAUSE]
    assert stops == 1

    waiting = controller.MicState()
    waiting.state = "DICTATING"
    waiting.speech_seen_in_chunk = True
    waiting.chunk_started_at = now
    waiting.last_handy_ui_check = now
    waiting.last_speech_at = now - 1.6
    waiting.dict_speech_frames = [frame.copy() for _ in range(7)]
    waiting.dict_tail_frames.extend(frame.copy() for _ in range(7))
    jobs: queue.Queue = queue.Queue(maxsize=1)
    waiting.handle_dictating_frame(frame, now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, jobs)
    assert waiting.state == "DICTATING"
    assert stops == 1
    assert waiting.whisper_pending is not None
    assert waiting.whisper_pending["kind"] == "fast_cmd"
    job = jobs.get_nowait()
    assert "send prompt" in job["prompt"]
    assert posted == ["stop"]


def test_dictation_idle_timeout_cancels_handy_without_calling_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # handy_cancel talks to the live app. write_status replaces status.json.
    import queue

    cancelled = 0
    cues: list[str] = []

    def cancel(*_args: object, **_kwargs: object) -> bool:
        nonlocal cancelled
        cancelled += 1
        return True

    monkeypatch.setattr(controller, "handy_cancel", cancel)
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    for name in (
        "silence_speech",
        "stop_playback",
        "handy_stop_recording",
        "handy_start_recording",
        "dispatch_transcript",
        "pause_tts_clips",
        "kill_tts_clips",
        "bridge_request",
    ):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def tick(elapsed: float, speech: bool) -> controller.MicState:
        mic = controller.MicState()
        mic.state = "DICTATING"
        now = 100.0
        mic.chunk_started_at = now - elapsed
        mic.last_handy_ui_check = now
        mic.last_speech_at = mic.chunk_started_at
        mic.handle_dictating_frame(
            np.zeros(1280, dtype=np.int16), now, 0.0, 0.0, speech, _Reset(), _Reset(), 5.0, 15.0, queue.Queue()
        )
        return mic

    waiting = tick(14.0, False)
    assert waiting.state == "DICTATING"
    assert cancelled == 0
    assert cues == []

    heard = tick(20.0, True)
    assert heard.state == "DICTATING"
    assert heard.speech_seen_in_chunk is True
    assert cancelled == 0

    expired = tick(15.0, False)
    assert expired.state == "IDLE"
    assert cancelled == 1
    assert cues == [controller.SOUND_PAUSE]
    assert expired.cooldown_until > controller.time.monotonic()


def test_partial_text_is_rewritten_without_posting_to_the_live_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    # bridge_request posts /transcript. The live session is on port 62283.
    posts: list[tuple[str, str, dict | None, str | None]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        assert path == "/transcript"
        posts.append((method, path, body, base))
        text = (body or {}).get("text")
        if text == "scratch that":
            return {"action": "scratched"}
        return {"action": "appended"}

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(controller, "resolve_delivery", lambda: (_ for _ in ()).throw(AssertionError("resolve_delivery")))

    mic = controller.MicState()
    mic.partial_base = "http://127.0.0.1:9"
    mic.show_partial("hello there")
    assert posts == [("POST", "/transcript", {"text": "hello there"}, "http://127.0.0.1:9")]
    assert mic.partial_shown == "hello there"

    mic.show_partial("hello there")
    assert len(posts) == 1

    mic.show_partial("send that")
    assert mic.partial_shown == "hello there"
    assert len(posts) == 1

    mic.show_partial("hello send that")
    assert [post[2] for post in posts[1:]] == [{"text": "scratch that"}, {"text": "hello"}]
    assert mic.partial_shown == "hello"

    mic.show_partial("please pause")
    assert posts[-2][2] == {"text": "scratch that"}
    assert posts[-1][2] == {"text": "please pause\u2060"}
    assert mic.partial_shown == "please pause\u2060"

    mic.retract_partial()
    assert posts[-1][2] == {"text": "scratch that"}
    assert mic.partial_shown == ""
    assert mic.partial_base == ""


def test_dispatch_rewrites_a_send_on_a_v2_bridge_without_posting_live(monkeypatch: pytest.MonkeyPatch) -> None:
    # resolve_delivery would select pid 16590. fallback_macos_inject types into the focused app.
    calls: list[tuple[str, str, dict | None, str | None]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        calls.append((method, path, body, base))
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            return {"ok": True, "action": "appended", "draft": (body or {}).get("text", "")}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    for name in ("paste_into_focus", "fallback_macos_inject"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    assert controller.dispatch_transcript("  ") == {"action": "noop", "draft": ""}
    assert calls == []

    sent = controller.dispatch_transcript("all done")
    assert sent["draft"] == "send prompt"
    assert calls[-1] == ("POST", "/transcript", {"text": "send prompt"}, "http://127.0.0.1:9")

    heard = controller.dispatch_transcript("scratch that")
    assert heard["draft"] == "scratch that"
    assert calls[-1][2] == {"text": "scratch that"}

    plain = controller.dispatch_transcript("hello there")
    assert plain["draft"] == "hello there"

    controller.PRESERVED_PAUSE = ""
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please stop"
        assert controller.PRESERVED_PAUSE
    finally:
        controller.PRESERVED_PAUSE = ""


def test_a_held_sentence_is_sent_once(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")),
    )
    controller._undelivered_transcript = "Ship the notes."
    try:
        first = controller.dispatch_transcript("all done")
        assert first["draft"] == "Ship the notes. send prompt"
        assert posts == ["Ship the notes. send prompt"]
        assert controller._undelivered_transcript == ""
        second = controller.dispatch_transcript("all done")
        assert second["draft"] == "send prompt"
        assert posts == ["Ship the notes. send prompt", "send prompt"]

        def bridge_v1(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
            assert base == "http://127.0.0.1:9"
            if method == "GET" and path == "/status":
                return {"ok": True, "version": 1, "draft": ""}
            if method == "POST" and path == "/transcript":
                posts.append(str((body or {}).get("text", "")))
                return {"ok": True, "action": "sent", "draft": posts[-1]}
            raise AssertionError(path)

        posts.clear()
        controller._undelivered_transcript = "Ship the notes."
        monkeypatch.setattr(controller, "bridge_request", bridge_v1)
        older = controller.dispatch_transcript("all done")
        assert older["draft"] == "Ship the notes. send prompt"
        assert posts == ["Ship the notes. send prompt"]
        assert controller._undelivered_transcript == ""
        controller.dispatch_transcript("all done")
        assert posts[-1] == "send prompt"
    finally:
        controller._undelivered_transcript = ""


def test_a_failed_send_keeps_the_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    version = {"n": 2}
    accept = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": version["n"], "draft": ""}
        if method == "POST" and path == "/transcript":
            if not accept["ok"]:
                return None
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")),
    )
    controller._undelivered_transcript = "Ship the notes."
    try:
        held = controller.dispatch_transcript("all done")
        assert held == {"action": "held", "draft": "Ship the notes."}
        assert posts == []
        assert controller._undelivered_transcript == "Ship the notes."
        accept["ok"] = True
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. send prompt"
        assert posts == ["Ship the notes. send prompt"]
        assert controller._undelivered_transcript == ""

        posts.clear()
        accept["ok"] = False
        version["n"] = 1
        controller._undelivered_transcript = "Ship the notes."
        held_v1 = controller.dispatch_transcript("all done")
        assert held_v1 == {"action": "held", "draft": "Ship the notes."}
        assert posts == []
        accept["ok"] = True
        sent_v1 = controller.dispatch_transcript("all done")
        assert sent_v1["draft"] == "Ship the notes. send prompt"
        assert posts == ["Ship the notes. send prompt"]
        assert controller._undelivered_transcript == ""
    finally:
        controller._undelivered_transcript = ""


def test_a_failed_send_keeps_the_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    version = {"n": 2}
    accept = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": version["n"], "draft": ""}
        if method == "POST" and path == "/transcript":
            if not accept["ok"]:
                return None
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    try:
        held = controller.dispatch_transcript("ship all done")
        assert held == {"action": "held", "draft": "Ship the notes. ship"}
        again = controller.dispatch_transcript("ship all done")
        assert again["draft"] == "Ship the notes. ship"
        assert posts == []
        accept["ok"] = True
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship send prompt"
        assert posts == ["Ship the notes. ship send prompt"]
        assert controller._undelivered_transcript == ""

        posts.clear()
        accept["ok"] = False
        version["n"] = 1
        controller._undelivered_transcript = "Ship the notes."
        held_v1 = controller.dispatch_transcript("ship all done")
        assert held_v1 == {"action": "held", "draft": "Ship the notes. ship"}
        assert posts == []
        accept["ok"] = True
        sent_v1 = controller.dispatch_transcript("all done")
        assert sent_v1["draft"] == "Ship the notes. ship send prompt"
        assert controller._undelivered_transcript == ""
    finally:
        controller._undelivered_transcript = ""
        controller.PRESERVED_PAUSE = ""


def test_a_retried_send_posts_the_prefix_once(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    version = {"n": 2}
    accept = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": version["n"], "draft": ""}
        if method == "POST" and path == "/transcript":
            if not accept["ok"]:
                return None
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    try:
        failed = controller.dispatch_transcript("ship all done")
        assert failed == {"action": "held", "draft": "Ship the notes. ship"}
        accept["ok"] = True
        sent = controller.dispatch_transcript("ship all done")
        assert sent["draft"] == "Ship the notes. ship send prompt"
        assert posts == ["Ship the notes. ship send prompt"]
        assert controller._undelivered_transcript == ""
        again = controller.dispatch_transcript("ship all done")
        assert again["draft"] == "ship send prompt"
        assert posts == ["Ship the notes. ship send prompt", "ship send prompt"]

        posts.clear()
        accept["ok"] = False
        version["n"] = 1
        controller._undelivered_transcript = "Ship the notes."
        controller.dispatch_transcript("ship all done")
        accept["ok"] = True
        sent_v1 = controller.dispatch_transcript("ship all done")
        assert sent_v1["draft"] == "Ship the notes. ship send prompt"
        assert posts == ["Ship the notes. ship send prompt"]
        assert controller._undelivered_transcript == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_note_leaves_the_send_prefix_held(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    version = {"n": 2}
    accept = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": version["n"], "draft": ""}
        if method == "POST" and path == "/transcript":
            if not accept["ok"]:
                return None
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "appended", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = ""
    try:
        failed = controller.dispatch_transcript("ship all done")
        assert failed == {"action": "held", "draft": "Ship the notes. ship"}
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship"
        accept["ok"] = True
        noted = controller.dispatch_transcript("Thanks.")
        assert noted["draft"] == "Ship the notes. Thanks."
        assert posts == ["Ship the notes. Thanks."]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == "ship"
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "ship send prompt"
        assert posts == ["Ship the notes. Thanks.", "ship send prompt"]
        assert controller._pending_send_prefix == ""

        posts.clear()
        accept["ok"] = False
        version["n"] = 1
        controller._undelivered_transcript = "Ship the notes."
        controller.dispatch_transcript("ship all done")
        accept["ok"] = True
        noted_v1 = controller.dispatch_transcript("Thanks.")
        assert noted_v1["draft"] == "Ship the notes. Thanks."
        assert controller._pending_send_prefix == "ship"
        sent_v1 = controller.dispatch_transcript("all done")
        assert sent_v1["draft"] == "ship send prompt"
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_dead_status_does_not_press_enter_while_a_prefix_is_held(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    monkeypatch.setattr(controller, "bridge_request", lambda *_a, **_k: None)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship"
    try:
        held = controller.dispatch_transcript("all done")
        assert held == {"action": "held", "draft": "Ship the notes. ship"}
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship"
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        sent = controller.dispatch_transcript("all done")
        assert sent["action"] == "sent"
        assert injected == [("", "sent")]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_dead_status_does_not_type_a_held_send_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    monkeypatch.setattr(controller, "bridge_request", lambda *_a, **_k: None)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship"
    try:
        held = controller.dispatch_transcript("ship all done")
        assert held == {"action": "held", "draft": "Ship the notes. ship"}
        again = controller.dispatch_transcript("ship all done")
        assert again["draft"] == "Ship the notes. ship"
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship"
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        sent = controller.dispatch_transcript("ship all done")
        assert sent["action"] == "sent"
        assert injected == [("ship", "sent")]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_recovered_status_sends_the_held_prefix_once(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []
    up = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if not up["ok"]:
            return None
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship"
    try:
        failed = controller.dispatch_transcript("ship all done")
        assert failed == {"action": "held", "draft": "Ship the notes. ship"}
        assert injected == []
        up["ok"] = True
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship send prompt"
        assert posts == ["Ship the notes. ship send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        again = controller.dispatch_transcript("all done")
        assert again["draft"] == "send prompt"
        assert posts == ["Ship the notes. ship send prompt", "send prompt"]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_recovered_post_keeps_the_held_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []
    accept = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            if not accept["ok"]:
                return None
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship"
    try:
        failed = controller.dispatch_transcript("all done")
        assert failed == {"action": "held", "draft": "Ship the notes. ship"}
        assert posts == []
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship"
        accept["ok"] = True
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship send prompt"
        assert posts == ["Ship the notes. ship send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        again = controller.dispatch_transcript("all done")
        assert again["draft"] == "send prompt"
        assert posts == ["Ship the notes. ship send prompt", "send prompt"]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_second_prefix_stays_with_the_held_send(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []
    up = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if not up["ok"]:
            return None
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship"
    try:
        held = controller.dispatch_transcript("please all done")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        again = controller.dispatch_transcript("please all done")
        assert again["draft"] == "Ship the notes. ship please"
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        up["ok"] = True
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["Ship the notes. ship please send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        controller.dispatch_transcript("all done")
        assert posts == ["Ship the notes. ship please send prompt", "send prompt"]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_an_up_bridge_sends_both_prefixes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship"
    try:
        sent = controller.dispatch_transcript("please all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["Ship the notes. ship please send prompt"]
        assert injected == []
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        again = controller.dispatch_transcript("please all done")
        assert again["draft"] == "please send prompt"
        assert posts == ["Ship the notes. ship please send prompt", "please send prompt"]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_please_send_keeps_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []
    accept = {"ok": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            if not accept["ok"]:
                return None
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "sent", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship"
    try:
        failed = controller.dispatch_transcript("please all done")
        assert failed == {"action": "held", "draft": "Ship the notes. ship please"}
        assert posts == []
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        accept["ok"] = True
        sent = controller.dispatch_transcript("please all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["Ship the notes. ship please send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        again = controller.dispatch_transcript("please all done")
        assert again["draft"] == "please send prompt"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_scratch_leaves_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "appended", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        scratched = controller.dispatch_transcript("scratch that")
        assert posts == ["scratch that"]
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["scratch that", "Ship the notes. ship please send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_pause_leaves_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "paused", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please stop"
        assert posts == ["please stop"]
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["please stop", "Ship the notes. ship please send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_v1_pause_leaves_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "paused", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please pause listening"
        assert posts == ["please pause listening"]
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["please pause listening", "Ship the notes. ship please send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v1_pause_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("please stop")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v2_pause_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("please stop")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v2_scratch_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("scratch that")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v1_scratch_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("scratch that")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v2_clear_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("clear draft")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v1_clear_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("clear draft")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_successful_v2_clear_drops_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "cleared", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        cleared = controller.dispatch_transcript("clear draft")
        assert cleared["draft"] == "clear draft"
        assert posts == ["clear draft"]
        assert injected == []
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "send prompt"
        assert posts == ["clear draft", "send prompt"]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_successful_v1_clear_drops_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "cleared", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        cleared = controller.dispatch_transcript("clear draft")
        assert cleared["draft"] == "clear draft"
        assert posts == ["clear draft"]
        assert injected == []
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "send prompt"
        assert posts == ["clear draft", "send prompt"]
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_clear_drops_the_pause_line_before_the_next_send(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "appended", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please stop"
        assert controller.PRESERVED_PAUSE == "please"
        cleared = controller.dispatch_transcript("clear draft")
        assert cleared["draft"] == "clear draft"
        assert controller.PRESERVED_PAUSE == ""
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "send prompt"
        assert posts == ["please stop", "clear draft", "send prompt"]
        assert injected == []
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_clear_keeps_the_pause_line(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []
    fail_clear = {"on": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            text = str((body or {}).get("text", ""))
            if fail_clear["on"] and text == "clear draft":
                return None
            posts.append(text)
            return {"ok": True, "action": "appended", "draft": text}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please stop"
        assert controller.PRESERVED_PAUSE == "please"
        fail_clear["on"] = True
        held = controller.dispatch_transcript("clear draft")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert controller.PRESERVED_PAUSE == "please"
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        assert injected == []
        fail_clear["on"] = False
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["please stop", "Ship the notes. ship please send prompt"]
        assert controller.PRESERVED_PAUSE == ""
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v1_clear_keeps_the_pause_line(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []
    fail_clear = {"on": False}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            text = str((body or {}).get("text", ""))
            if fail_clear["on"] and text == "clear draft":
                return None
            posts.append(text)
            return {"ok": True, "action": "appended", "draft": text}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please pause listening"
        assert posts == ["please pause listening"]
        assert controller.PRESERVED_PAUSE == "please"
        fail_clear["on"] = True
        held = controller.dispatch_transcript("clear draft")
        assert held == {"action": "held", "draft": "Ship the notes. ship please"}
        assert controller.PRESERVED_PAUSE == "please"
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        assert injected == []
        fail_clear["on"] = False
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["please pause listening", "Ship the notes. ship please send prompt"]
        assert controller.PRESERVED_PAUSE == ""
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_v1_clear_drops_the_pause_line_before_the_next_send(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "appended", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please pause listening"
        assert controller.PRESERVED_PAUSE == "please"
        cleared = controller.dispatch_transcript("clear draft")
        assert cleared["draft"] == "clear draft"
        assert controller.PRESERVED_PAUSE == ""
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "send prompt"
        assert posts == ["please pause listening", "clear draft", "send prompt"]
        assert injected == []
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_cancel_leaves_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "cancelled", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        cancelled = controller.dispatch_transcript("cancel")
        assert cancelled["draft"] == "cancel"
        assert posts == ["cancel"]
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["cancel", "Ship the notes. ship please send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v2_cancel_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("cancel")
        assert held == {
            "action": "cancelled",
            "draft": "Ship the notes. ship please",
            "strippedCommand": "cancel",
        }
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_failed_v1_cancel_keeps_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            return None
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        held = controller.dispatch_transcript("cancel")
        assert held == {
            "action": "cancelled",
            "draft": "Ship the notes. ship please",
            "strippedCommand": "cancel",
        }
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_v1_cancel_leaves_the_sentence_and_both_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    injected: list[tuple[str, str]] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "cancelled", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        cancelled = controller.dispatch_transcript("cancel")
        assert cancelled["draft"] == "cancel"
        assert posts == ["cancel"]
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. ship please send prompt"
        assert posts == ["cancel", "Ship the notes. ship please send prompt"]
        assert controller._undelivered_transcript == ""
        assert controller._pending_send_prefix == ""
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_a_dead_status_does_not_type_cancel_while_both_holds_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    injected: list[tuple[str, str]] = []

    monkeypatch.setattr(controller, "bridge_request", lambda *_a, **_k: None)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        cancelled = controller.dispatch_transcript("cancel")
        assert cancelled["action"] == "cancelled"
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_scratch_and_pause_leave_a_held_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    posts: list[str] = []
    version = {"n": 2}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": version["n"], "draft": ""}
        if method == "POST" and path == "/transcript":
            posts.append(str((body or {}).get("text", "")))
            return {"ok": True, "action": "appended", "draft": posts[-1]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(
        controller,
        "fallback_macos_inject",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("keys")),
    )
    controller._undelivered_transcript = "Ship the notes."
    controller.PRESERVED_PAUSE = ""
    try:
        controller.dispatch_transcript("scratch that")
        controller.dispatch_transcript("please stop")
        assert posts == ["scratch that", "please stop"]
        assert controller._undelivered_transcript == "Ship the notes."
        version["n"] = 1
        posts.clear()
        controller.PRESERVED_PAUSE = ""
        controller.dispatch_transcript("scratch that")
        controller.dispatch_transcript("please stop")
        assert posts == ["scratch that", "please pause listening"]
        assert controller._undelivered_transcript == "Ship the notes."
        controller.PRESERVED_PAUSE = ""
        sent = controller.dispatch_transcript("all done")
        assert sent["draft"] == "Ship the notes. send prompt"
        assert controller._undelivered_transcript == ""
    finally:
        controller.PRESERVED_PAUSE = ""
        controller._undelivered_transcript = ""


def test_v1_dispatch_rewrites_a_pause_without_sending_keystrokes(monkeypatch: pytest.MonkeyPatch) -> None:
    # The v1 path deletes already-pasted characters with osascript key code 51.
    posts: list[dict | None] = []
    scripts: list[str] = []
    draft = {"text": ""}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 1, "draft": draft["text"]}
        if method == "POST" and path == "/transcript":
            posts.append(body)
            return {"ok": True, "action": "appended", "draft": (body or {}).get("text", "")}
        raise AssertionError(path)

    def run(argv: list[str], **_kwargs: object) -> object:
        assert argv[0] == "/usr/bin/osascript"
        scripts.append(argv[2])
        return subprocess.CompletedProcess(argv, 0)

    import subprocess

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False},
    )
    monkeypatch.setattr(controller.subprocess, "run", run)
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)
    for name in ("paste_into_focus", "fallback_macos_inject"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    draft["text"] = "hello there"
    kept = controller.dispatch_transcript("hello there")
    assert kept == {"action": "appended", "draft": "hello there"}
    assert posts == []
    assert scripts == []

    draft["text"] = ""
    sent = controller.dispatch_transcript("all done")
    assert sent["draft"] == "send prompt"
    assert posts[-1] == {"text": "send prompt"}
    assert scripts == []

    controller.PRESERVED_PAUSE = ""
    try:
        draft["text"] = "please stop"
        paused = controller.dispatch_transcript("please stop")
        assert paused["draft"] == "please pause listening"
        assert posts[-1] == {"text": "please pause listening"}
        assert scripts == ['tell application "System Events" to repeat 11 times\nkey code 51\nend repeat']
    finally:
        controller.PRESERVED_PAUSE = ""


def test_paste_delivery_types_a_plan_without_touching_the_focused_app(monkeypatch: pytest.MonkeyPatch) -> None:
    # paste_into_focus calls fallback_macos_inject, which types into the focused app.
    injected: list[tuple[str, str]] = []
    posts: list[dict | None] = []
    draft = {"text": ""}

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        if method == "GET" and path == "/status":
            return {"ok": True, "version": 2, "draft": draft["text"]}
        if method == "POST" and path == "/transcript":
            posts.append(body)
            return {"ok": True, "action": "paused", "draft": draft["text"]}
        raise AssertionError(path)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(
        controller,
        "resolve_delivery",
        lambda: {"mode": "paste", "port": 9, "pid": 1, "focused_text": True},
    )
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )

    assert controller.dispatch_transcript("  ")["action"] == "noop"
    assert injected == []

    plain = controller.dispatch_transcript("hello there")
    assert plain["action"] == "appended"
    assert plain["via"] == "focus"
    assert injected == [("hello there ", "appended")]
    assert posts == []

    scratched = controller.dispatch_transcript("scratch that")
    assert scratched["action"] == "scratched"
    assert scratched["via"] == "focus"
    assert len(injected) == 1

    sent = controller.dispatch_transcript("ship all done")
    assert sent["action"] == "sent"
    assert sent["via"] == "focus"
    assert injected[-1] == ("ship", "sent")
    assert posts == []

    controller.PRESERVED_PAUSE = ""
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["action"] == "paused"
        assert posts == [{"text": "please stop"}]
        assert len(injected) == 2
    finally:
        controller.PRESERVED_PAUSE = ""

    controller.PRESERVED_PAUSE = "remember this"
    draft["text"] = "remember this"
    try:
        kept = controller.dispatch_transcript("ship all done")
        assert kept["action"] == "sent"
        assert injected[-1] == ("remember this ship", "sent")
        assert posts[-1] == {"text": "clear draft"}
    finally:
        controller.PRESERVED_PAUSE = ""


def test_a_dead_bridge_types_a_scratch_unless_focus_is_text(monkeypatch: pytest.MonkeyPatch) -> None:
    # A non-command is held once. Commands still fall through to keystrokes.
    injected: list[tuple[str, str]] = []
    dest = {"mode": "bridge", "port": 9, "pid": 1, "focused_text": False}

    monkeypatch.setattr(controller, "bridge_request", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "resolve_delivery", lambda: dest)
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    controller._undelivered_transcript = ""
    controller._pending_send_prefix = ""
    monkeypatch.setattr(
        controller.subprocess,
        "run",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("subprocess")),
    )
    controller.PRESERVED_PAUSE = ""

    plain = controller.dispatch_transcript("hello there")
    assert plain == {"action": "held", "draft": "hello there"}
    again = controller.dispatch_transcript("hello there")
    assert again == {"action": "held", "draft": "hello there"}
    assert injected == []

    sent = controller.dispatch_transcript("ship all done")
    assert sent["action"] == "sent"
    assert injected[-1] == ("ship", "sent")

    controller.PRESERVED_PAUSE = ""
    try:
        paused = controller.dispatch_transcript("please stop")
        assert paused["action"] == "paused"
        assert injected[-1] == ("please ", "paused")
    finally:
        controller.PRESERVED_PAUSE = ""

    cancelled = controller.dispatch_transcript("cancel")
    assert cancelled["action"] == "cancelled"
    assert len(injected) == 2

    typed = controller.dispatch_transcript("scratch that")
    assert typed == {"action": "appended", "draft": "scratch that"}
    assert injected[-1] == ("scratch that ", "appended")

    dest["focused_text"] = True
    focused = controller.dispatch_transcript("scratch that")
    assert focused["action"] == "scratched"
    assert focused["via"] == "focus"
    assert injected[-1] == ("scratch that ", "appended")
    controller._undelivered_transcript = ""


def test_handy_closed_or_fn_release_returns_idle_without_restarting_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    # handy_process_running and handy_stop_recording talk to the live app.
    import queue

    posted: list[str] = []
    cues: list[str] = []
    flags = {"fn": False, "process": True, "window": False, "stops": 0, "cancels": 0}
    rows: list[tuple[int, str] | None] = []

    monkeypatch.setattr(controller, "fn_held", lambda: flags["fn"])
    monkeypatch.setattr(controller, "handy_process_running", lambda: flags["process"])
    monkeypatch.setattr(controller, "handy_window_open", lambda: flags["window"])
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "wait_for_new_history_row", lambda _prev, timeout_sec=2.2: rows[0] if rows else None)
    monkeypatch.setattr(controller, "dispatch_transcript", lambda text: posted.append(text) or {"action": "sent", "draft": text})
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)

    def stop() -> bool:
        flags["stops"] += 1
        return True

    def cancel(*_a: object, **_k: object) -> bool:
        flags["cancels"] += 1
        return True

    monkeypatch.setattr(controller, "handy_stop_recording", stop)
    monkeypatch.setattr(controller, "handy_cancel", cancel)
    for name in ("handy_start_recording", "silence_speech", "stop_playback", "bridge_request", "pause_tts_clips", "kill_tts_clips"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def frame(mic: controller.MicState, now: float) -> None:
        mic.handle_dictating_frame(
            np.zeros(1280, dtype=np.int16), now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue()
        )

    hidden = controller.MicState()
    hidden.state = "DICTATING"
    hidden.chunk_started_at = 10.0
    flags["process"] = True
    flags["window"] = False
    frame(hidden, 12.0)
    assert hidden.state == "DICTATING"
    assert hidden.handy_ui_seen is False
    assert cues == []

    closed = controller.MicState()
    closed.state = "DICTATING"
    closed.chunk_started_at = 10.0
    flags["process"] = False
    before = controller.time.monotonic()
    frame(closed, 12.0)
    assert closed.state == "IDLE"
    assert cues == [controller.SOUND_PAUSE]
    assert closed.score_wake_blocked_until >= before + 45
    assert posted == []
    assert flags["stops"] == 0

    seen = controller.MicState()
    seen.state = "DICTATING"
    seen.chunk_started_at = 10.0
    flags["process"] = True
    flags["window"] = True
    frame(seen, 12.0)
    assert seen.handy_ui_seen is True
    assert seen.state == "DICTATING"
    flags["window"] = False
    frame(seen, 13.1)
    assert seen.state == "IDLE"
    assert cues[-1] == controller.SOUND_PAUSE

    released = controller.MicState()
    released.state = "DICTATING"
    released.fn_was_down = True
    released.chunk_started_at = 10.0
    released.last_history_id = 3
    flags["fn"] = False
    rows.append((8, "ship all done"))
    frame(released, 12.0)
    assert released.state == "IDLE"
    assert posted == ["ship all done"]
    assert cues[-1] == controller.SOUND_PAUSE
    assert flags["stops"] == 0
    assert flags["cancels"] == 0


def test_a_handy_row_during_dictation_is_dispatched_before_the_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    # A new history row is not the silence flush. Scratch restarts Handy with the tick, not the cancel cue.
    import queue

    posted: list[str] = []
    cues: list[str] = []
    starts = 0
    row = {"id": 3, "text": ""}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        matched = controller.match_command(text)
        return {"action": matched["action"] if matched else "appended", "draft": text}

    def start(*_a: object, **_k: object) -> bool:
        nonlocal starts
        starts += 1
        return True

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (row["id"], row["text"]))
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "handy_start_recording", start)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)
    for name in ("handy_stop_recording", "handy_cancel", "silence_speech", "stop_playback", "bridge_request", "pause_tts_clips", "kill_tts_clips"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def tick(text: str | None) -> controller.MicState:
        nonlocal starts
        starts = 0
        mic = controller.MicState()
        mic.state = "DICTATING"
        mic.last_history_id = 3
        mic.speech_seen_in_chunk = True
        mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
        now = 50.0
        mic.chunk_started_at = now
        mic.last_speech_at = now
        mic.last_handy_ui_check = now
        if text is None:
            row["id"] = 3
            row["text"] = ""
        else:
            row["id"] = 8
            row["text"] = text
        mic.handle_dictating_frame(
            np.zeros(1280, dtype=np.int16), now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue()
        )
        return mic

    waiting = tick(None)
    assert waiting.state == "DICTATING"
    assert posted == []
    assert starts == 0

    sent = tick("all done")
    assert sent.state == "IDLE"
    assert posted == ["all done"]
    assert cues == [controller.SOUND_SEND]
    assert starts == 0
    assert sent.speech_seen_in_chunk is False

    scratched = tick("scratch that")
    assert scratched.state == "DICTATING"
    assert posted[-1] == "scratch that"
    assert cues[-1] == controller.SOUND_CHUNK_TICK
    assert starts == 1
    assert scratched.dict_speech_frames == []

    paused = tick("stop")
    assert paused.state == "IDLE"
    assert posted[-1] == "stop"
    assert cues[-1] == controller.SOUND_PAUSE
    assert starts == 0

    cancelled = tick("cancel")
    assert cancelled.state == "IDLE"
    assert posted[-1] == "cancel"
    assert cues[-1] == controller.SOUND_CANCEL
    assert starts == 0
    assert cancelled.speech_seen_in_chunk is False


def test_a_held_send_row_stays_dictating_and_keeps_both_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    import queue

    posted: list[str] = []
    injected: list[tuple[str, str]] = []
    starts = 0
    row = {"id": 8, "text": "ship all done"}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        return {"action": "held", "draft": "Ship the notes. ship please"}

    def start(*_a: object, **_k: object) -> bool:
        nonlocal starts
        starts += 1
        return True

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (row["id"], row["text"]))
    monkeypatch.setattr(controller, "play_cue", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "handy_start_recording", start)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "fallback_macos_inject", lambda text, action: injected.append((text, action)))
    monkeypatch.setattr(controller.time, "sleep", lambda _seconds: None)
    for name in ("handy_stop_recording", "handy_cancel", "silence_speech", "stop_playback", "bridge_request", "pause_tts_clips", "kill_tts_clips"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    controller.PRESERVED_PAUSE = ""
    controller._undelivered_transcript = "Ship the notes."
    controller._pending_send_prefix = "ship please"
    try:
        mic = controller.MicState()
        mic.state = "DICTATING"
        mic.last_history_id = 3
        mic.speech_seen_in_chunk = True
        mic.dict_speech_frames = [np.zeros(1280, dtype=np.int16)]
        now = 50.0
        mic.chunk_started_at = now
        mic.last_speech_at = now
        mic.last_handy_ui_check = now
        mic.handle_dictating_frame(
            np.zeros(1280, dtype=np.int16), now, 0.0, 0.0, False, _Reset(), _Reset(), 5.0, 15.0, queue.Queue()
        )
        assert mic.state == "DICTATING"
        assert posted == ["ship all done"]
        assert starts == 1
        assert injected == []
        assert controller._undelivered_transcript == "Ship the notes."
        assert controller._pending_send_prefix == "ship please"
    finally:
        controller._undelivered_transcript = ""
        controller._pending_send_prefix = ""
        controller.PRESERVED_PAUSE = ""


def test_headphones_keep_a_quiet_frame_and_wait_longer_to_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    # The room mic drops a quiet frame. Headphones keep it, and the flush waits 8 s instead of 5.
    import queue

    stops = 0
    cues: list[str] = []

    def stop() -> bool:
        nonlocal stops
        stops += 1
        return False

    monkeypatch.setattr(controller, "handy_stop_recording", stop)
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    for name in ("handy_start_recording", "handy_cancel", "dispatch_transcript", "silence_speech", "stop_playback", "bridge_request"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def mic_at(headphones: bool, heard_for: float) -> controller.MicState:
        mic = controller.MicState()
        mic.state = "DICTATING"
        mic.on_headphones = headphones
        now = 30.0
        mic.chunk_started_at = now
        mic.last_handy_ui_check = now
        mic.last_speech_at = now - heard_for
        return mic

    def tick(mic: controller.MicState, speech: bool, vad: float, rms: float) -> None:
        mic.handle_dictating_frame(
            np.zeros(1280, dtype=np.int16), 30.0, rms, vad, speech, _Reset(), _Reset(), 5.0, 15.0, queue.Queue()
        )

    room = mic_at(False, 0.0)
    tick(room, False, 0.2, 40.0)
    assert room.speech_seen_in_chunk is False
    assert room.dict_speech_frames == []
    assert stops == 0

    phones = mic_at(True, 0.0)
    tick(phones, False, 0.2, 40.0)
    assert phones.speech_seen_in_chunk is True
    assert len(phones.dict_speech_frames) == 1

    quieter = mic_at(True, 0.0)
    tick(quieter, False, 0.0, 10.0)
    assert quieter.speech_seen_in_chunk is False

    spoken = mic_at(False, 0.0)
    tick(spoken, True, 0.0, 0.0)
    assert spoken.speech_seen_in_chunk is True

    early = mic_at(True, 6.0)
    early.speech_seen_in_chunk = True
    tick(early, False, 0.0, 0.0)
    assert early.state == "DICTATING"
    assert stops == 0

    room_flush = mic_at(False, 6.0)
    room_flush.speech_seen_in_chunk = True
    tick(room_flush, False, 0.0, 0.0)
    assert room_flush.state == "IDLE"
    assert stops == 1
    assert cues == [controller.SOUND_PAUSE]

    phone_flush = mic_at(True, 8.0)
    phone_flush.speech_seen_in_chunk = True
    tick(phone_flush, False, 0.0, 0.0)
    assert phone_flush.state == "IDLE"
    assert stops == 2


def test_eighteen_loud_frames_queue_a_partial_without_flushing_handy(monkeypatch: pytest.MonkeyPatch) -> None:
    # maybe_emit_partial transcribes the open chunk. It must not stop Handy.
    import queue

    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (0, ""))
    monkeypatch.setattr(controller, "write_status", lambda *_a, **_k: None)
    for name in (
        "handy_stop_recording",
        "handy_start_recording",
        "handy_cancel",
        "dispatch_transcript",
        "silence_speech",
        "stop_playback",
        "bridge_request",
        "play_cue",
    ):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    def feed(level: int, count: int) -> tuple[controller.MicState, queue.Queue]:
        mic = controller.MicState()
        mic.state = "DICTATING"
        now = 40.0
        mic.chunk_started_at = now
        mic.last_speech_at = now
        mic.last_handy_ui_check = now
        jobs: queue.Queue = queue.Queue(maxsize=1)
        frame = np.full(1280, level, dtype=np.int16)
        for _ in range(count):
            mic.handle_dictating_frame(frame, now, 500.0, 0.9, True, _Reset(), _Reset(), 5.0, 15.0, jobs)
        return mic, jobs

    short, short_jobs = feed(400, 17)
    assert short.state == "DICTATING"
    assert short.whisper_pending is None
    assert short_jobs.empty()

    quiet, quiet_jobs = feed(100, 18)
    assert quiet.state == "DICTATING"
    assert quiet.whisper_pending is None
    assert quiet_jobs.empty()

    loud, loud_jobs = feed(400, 18)
    assert loud.state == "DICTATING"
    assert loud.whisper_pending is not None
    assert loud.whisper_pending["kind"] == "partial"
    assert loud.partial_sent_frames == 18
    job = loud_jobs.get_nowait()
    assert job["prompt"] == "A person dictating a sentence."

    mic = loud
    mic.handle_dictating_frame(
        np.full(1280, 400, dtype=np.int16), 40.0, 500.0, 0.9, True, _Reset(), _Reset(), 5.0, 15.0, loud_jobs
    )
    assert mic.partial_sent_frames == 18
    assert mic.state == "DICTATING"
    assert loud_jobs.empty()


def test_closing_partial_posts_six_loud_frames_and_not_a_short_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    # show_closing_partial blocks on the worker slot. The bridge post must not hit port 62283.
    posts: list[dict | None] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        posts.append(body)
        text = (body or {}).get("text")
        if text == "scratch that":
            return {"action": "scratched"}
        return {"action": "appended"}

    class Jobs:
        def __init__(self, answer: str | None) -> None:
            self.answer = answer
            self.prompts: list[str] = []

        def put(self, item: dict, timeout: float | None = None) -> None:
            self.prompts.append(item["prompt"])
            if self.answer is None:
                raise RuntimeError("worker down")
            item["slot"].put(self.answer)

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(controller, "resolve_delivery", lambda: (_ for _ in ()).throw(AssertionError("resolve_delivery")))

    def frames(count: int, level: int) -> controller.MicState:
        mic = controller.MicState()
        mic.state = "DICTATING"
        mic.partial_base = "http://127.0.0.1:9"
        mic.dict_speech_frames = [np.full(1280, level, dtype=np.int16) for _ in range(count)]
        return mic

    short = frames(5, 400)
    short.show_closing_partial(Jobs("hello there"))  # type: ignore[arg-type]
    assert posts == []

    quiet = frames(6, 100)
    quiet_jobs = Jobs("hello there")
    quiet.show_closing_partial(quiet_jobs)  # type: ignore[arg-type]
    assert quiet_jobs.prompts == []
    assert posts == []

    gap = frames(6, 400)
    gap.partial_sent_frames = 3
    gap.show_closing_partial(Jobs("hello there"))  # type: ignore[arg-type]
    assert posts == []

    ready = frames(6, 400)
    ready_jobs = Jobs("hello there")
    ready.show_closing_partial(ready_jobs)  # type: ignore[arg-type]
    assert ready_jobs.prompts == ["A person dictating a sentence."]
    assert posts == [{"text": "hello there"}]
    assert ready.partial_shown == "hello there"
    assert ready.partial_sent_frames == 6

    blank = frames(6, 400)
    blank.show_closing_partial(Jobs("   "))  # type: ignore[arg-type]
    assert len(posts) == 1
    assert blank.partial_sent_frames == 0

    down = frames(6, 400)
    down.show_closing_partial(Jobs(None))  # type: ignore[arg-type]
    assert len(posts) == 1

    idle = controller.MicState()
    idle.state = "IDLE"
    idle.partial_base = "http://127.0.0.1:9"
    assert idle.apply_whisper("partial", "hello there", None, None) is False
    assert len(posts) == 1

    ready.apply_whisper("partial", "good night", None, None)
    assert posts[-2:] == [{"text": "scratch that"}, {"text": "good night"}]
    assert ready.partial_shown == "good night"


def test_fn_during_playback_cuts_speech_and_restarts_only_while_held(monkeypatch: pytest.MonkeyPatch) -> None:
    # The cut runs on a thread. Run it inline so silence_speech cannot reach the live clips.
    calls: list[tuple] = []
    clock = {"t": 1000.0}
    held = {"answers": [False]}

    class _Now:
        def __init__(self, target: object = None, daemon: bool = False) -> None:
            self.target = target

        def start(self) -> None:
            assert self.target is not None
            self.target()

    def fn_held() -> bool:
        if held["answers"]:
            return bool(held["answers"].pop(0))
        return False

    monkeypatch.setattr(controller.threading, "Thread", _Now)
    monkeypatch.setattr(controller.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(controller.time, "sleep", lambda seconds: clock.__setitem__("t", clock["t"] + float(seconds)))
    monkeypatch.setattr(controller, "fn_held", fn_held)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (11, "ignore me"))
    monkeypatch.setattr(controller, "kill_tts_clips", lambda: calls.append(("kill",)))
    monkeypatch.setattr(controller, "silence_speech", lambda flag: calls.append(("silence", flag)))
    monkeypatch.setattr(controller, "handy_cancel", lambda allow_launch=False: calls.append(("cancel", allow_launch)))
    monkeypatch.setattr(
        controller,
        "handy_start_recording",
        lambda allow_launch=False, fresh=False: calls.append(("start", allow_launch, fresh)),
    )
    for name in ("dispatch_transcript", "play_cue", "write_status", "stop_playback", "pause_tts_clips"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    class _Model:
        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {"hey_jarvis": 0.0}

        def reset(self) -> None:
            return None

    def press(tts: bool, answers: list[bool], was_down: bool = False) -> controller.MicState:
        calls.clear()
        held["answers"] = list(answers)
        mic = controller.MicState()
        mic.tts_active = tts
        mic.fn_was_down = was_down
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12
        mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
        frame = np.zeros(1280, dtype=np.int16)
        mic.handle_idle_frame(frame, clock["t"], 0.0, 0.0, False, "test", _Model(), None, "hey_jarvis", 0.5, __import__("queue").Queue())
        return mic

    idle = press(False, [True])
    assert calls == []
    assert idle.fn_was_down is True
    assert idle.state == "IDLE"

    repeat = press(True, [True], was_down=True)
    assert calls == []
    assert repeat.tts_active is True

    released = press(True, [True, False])
    assert ("silence", True) in calls
    assert ("kill",) in calls
    assert ("cancel", False) in calls
    assert not any(call[0] == "start" for call in calls)
    assert released.tts_active is False
    assert released.fn_cut_busy is False
    assert released.fn_ignore_through == 11
    assert released.state == "IDLE"

    still = press(True, [True, True])
    assert ("start", False, False) in calls
    assert still.fn_cut_busy is False
    assert still.state == "IDLE"


def test_idle_history_drops_a_row_recorded_over_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    # A row at or below fn_ignore_through was captured while the speakers were on.
    posted: list[str] = []
    cues: list[str] = []
    row = {"id": 0, "text": ""}

    def dispatch(text: str) -> dict[str, str]:
        posted.append(text)
        matched = controller.match_command(text)
        return {"action": matched["action"] if matched else "appended", "draft": text}

    monkeypatch.setattr(controller, "dispatch_transcript", dispatch)
    monkeypatch.setattr(controller, "latest_history_row", lambda: (row["id"], row["text"]))
    monkeypatch.setattr(controller, "play_cue", lambda sound, wait=False: cues.append(sound))
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    for name in ("silence_speech", "kill_tts_clips", "handy_start_recording", "handy_cancel", "write_status", "stop_playback", "pause_tts_clips"):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    class _Model:
        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {"hey_jarvis": 0.0}

        def reset(self) -> None:
            return None

    mic = controller.MicState()
    mic.last_history_id = 5
    mic.fn_ignore_through = 8
    mic.last_tts_check = 1e12
    mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
    frame = np.zeros(1280, dtype=np.int16)

    def tick(row_id: int, text: str, now: float) -> None:
        row["id"] = row_id
        row["text"] = text
        mic.last_manual_check = 0.0
        mic.handle_idle_frame(frame, now, 0.0, 0.0, False, "test", _Model(), None, "hey_jarvis", 0.5, __import__("queue").Queue())

    tick(7, "hello there", 10.0)
    assert mic.last_history_id == 7
    assert posted == []
    assert cues == []
    assert mic.state == "IDLE"

    tick(7, "hello there", 12.0)
    assert posted == []

    tick(9, "   ", 14.0)
    assert mic.last_history_id == 7
    assert posted == []

    tick(9, "all done", 16.0)
    assert mic.last_history_id == 9
    assert posted == ["all done"]
    assert cues == [controller.SOUND_SEND]

    tick(10, "scratch that", 18.0)
    assert posted[-1] == "scratch that"
    assert cues[-1] == controller.SOUND_CANCEL

    tick(11, "stop", 20.0)
    assert posted[-1] == "stop"
    assert cues[-1] == controller.SOUND_PAUSE

    tick(12, "cancel", 22.0)
    assert posted[-1] == "cancel"
    assert cues[-1] == controller.SOUND_PAUSE
    assert mic.state == "IDLE"


def test_a_short_utterance_queues_whisper_without_entering_dictation(monkeypatch: pytest.MonkeyPatch) -> None:
    # Path 2 runs only when the wake score stays under 0.5. enter_dictating must not run.
    import queue

    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    for name in (
        "silence_speech",
        "kill_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "dispatch_transcript",
        "play_cue",
        "write_status",
        "stop_playback",
        "pause_tts_clips",
    ):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    class _Model:
        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {"hey_jarvis": 0.0}

        def reset(self) -> None:
            return None

    def feed(speech: int, silence: int, level: int, pending: bool = False) -> tuple[controller.MicState, queue.Queue]:
        mic = controller.MicState()
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12
        mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
        if pending:
            mic.whisper_pending = {"kind": "busy", "slot": queue.Queue()}
        jobs: queue.Queue = queue.Queue(maxsize=1)
        now = 10.0
        model = _Model()
        for _ in range(speech):
            frame = np.full(1280, level, dtype=np.int16)
            rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
            mic.handle_idle_frame(frame, now, rms, 0.9, True, "test", model, None, "hey_jarvis", 0.5, jobs)
            now += 0.08
        for _ in range(silence):
            frame = np.zeros(1280, dtype=np.int16)
            mic.handle_idle_frame(frame, now, 0.0, 0.0, False, "test", model, None, "hey_jarvis", 0.5, jobs)
            now += 0.08
        return mic, jobs

    early, early_jobs = feed(1, 6, 500)
    assert early.state == "IDLE"
    assert early.whisper_pending is None
    assert early_jobs.empty()

    heard, heard_jobs = feed(1, 7, 500)
    assert heard.state == "IDLE"
    assert heard.whisper_pending is not None
    assert heard.whisper_pending["kind"] == "idle_verify"
    assert heard.idle_in_speech is False
    job = heard_jobs.get_nowait()
    assert job["prompt"].startswith("Hey Jarvis")

    quiet, quiet_jobs = feed(1, 7, 100)
    assert quiet.whisper_pending is None
    assert quiet_jobs.empty()

    long, long_jobs = feed(43, 7, 500)
    assert long.whisper_pending is None
    assert long.idle_in_speech is False
    assert long_jobs.empty()

    busy, busy_jobs = feed(1, 7, 500, pending=True)
    assert busy.whisper_pending is not None
    assert busy.whisper_pending["kind"] == "busy"
    assert busy.idle_verify_next is not None
    assert busy_jobs.empty()
    assert busy.state == "IDLE"


def test_a_held_idle_utterance_is_queued_when_whisper_is_free(monkeypatch: pytest.MonkeyPatch) -> None:
    # release_idle_utterance runs at the start of every idle frame.
    import queue

    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    for name in (
        "silence_speech",
        "kill_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "dispatch_transcript",
        "play_cue",
        "write_status",
        "stop_playback",
        "pause_tts_clips",
    ):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    class _Model:
        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {"hey_jarvis": 0.0}

        def reset(self) -> None:
            return None

    audio = np.array([0.25, -0.25], dtype=np.float32)
    prompt = "held clip"
    frame = np.zeros(1280, dtype=np.int16)

    def tick(mic: controller.MicState, jobs: queue.Queue) -> None:
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12
        mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
        mic.handle_idle_frame(frame, 10.0, 0.0, 0.0, False, "test", _Model(), None, "hey_jarvis", 0.5, jobs)

    free = controller.MicState()
    free.idle_verify_next = (audio, prompt)
    free_jobs: queue.Queue = queue.Queue(maxsize=1)
    tick(free, free_jobs)
    assert free.state == "IDLE"
    assert free.idle_verify_next is None
    assert free.whisper_pending is not None
    assert free.whisper_pending["kind"] == "idle_verify"
    job = free_jobs.get_nowait()
    assert job["prompt"] == "held clip"
    assert np.array_equal(job["audio"], audio)

    dropped = controller.MicState()
    dropped.state = "DICTATING"
    dropped.idle_verify_next = (audio, prompt)
    dropped_jobs: queue.Queue = queue.Queue(maxsize=1)
    tick(dropped, dropped_jobs)
    assert dropped.idle_verify_next is None
    assert dropped.whisper_pending is None
    assert dropped_jobs.empty()

    held = controller.MicState()
    held.whisper_pending = {"kind": "busy", "slot": queue.Queue()}
    held.idle_verify_next = (audio, prompt)
    held_jobs: queue.Queue = queue.Queue(maxsize=1)
    tick(held, held_jobs)
    assert held.idle_verify_next is not None
    assert np.array_equal(held.idle_verify_next[0], audio)
    assert held.idle_verify_next[1] == prompt
    assert held.whisper_pending["kind"] == "busy"
    assert held_jobs.empty()

    full = controller.MicState()
    full.idle_verify_next = (audio, prompt)
    full_jobs: queue.Queue = queue.Queue(maxsize=1)
    full_jobs.put({"placeholder": True})
    tick(full, full_jobs)
    assert full.idle_verify_next is not None
    assert np.array_equal(full.idle_verify_next[0], audio)
    assert full.idle_verify_next[1] == prompt
    assert full.whisper_pending is None
    assert full_jobs.qsize() == 1


def test_a_held_barge_clip_is_queued_even_during_dictation() -> None:
    # release_barge_clip does not care about state. A full queue or a busy slot keeps the hold.
    import queue

    audio = np.array([0.5, -0.5], dtype=np.float32)
    prompt = "Hey Jarvis. stop."

    idle = controller.MicState()
    assert idle.release_barge_clip(queue.Queue()) is False

    busy = controller.MicState()
    busy.whisper_pending = {"kind": "busy", "slot": queue.Queue()}
    busy.tts_barge_next = (audio, prompt)
    assert busy.release_barge_clip(queue.Queue()) is False
    assert busy.tts_barge_next is not None
    assert np.array_equal(busy.tts_barge_next[0], audio)
    assert busy.whisper_pending["kind"] == "busy"

    mic = controller.MicState()
    mic.state = "DICTATING"
    mic.tts_barge_next = (audio, prompt)
    jobs: queue.Queue = queue.Queue(maxsize=1)
    assert mic.release_barge_clip(jobs) is True
    assert mic.state == "DICTATING"
    assert mic.tts_barge_next is None
    assert mic.whisper_pending is not None
    assert mic.whisper_pending["kind"] == "tts_barge"
    job = jobs.get_nowait()
    assert job["prompt"] == prompt
    assert np.array_equal(job["audio"], audio)

    full = controller.MicState()
    full.tts_barge_next = (audio, prompt)
    blocked: queue.Queue = queue.Queue(maxsize=1)
    blocked.put({"placeholder": True})
    assert full.release_barge_clip(blocked) is False
    assert full.whisper_pending is None
    assert full.tts_barge_next is not None
    assert np.array_equal(full.tts_barge_next[0], audio)
    assert full.tts_barge_next[1] == prompt
    assert blocked.qsize() == 1


def test_a_failed_partial_scratch_keeps_the_old_text(monkeypatch: pytest.MonkeyPatch) -> None:
    # A scratch that does not return action scratched must not post the replacement.
    posts: list[dict | None] = []
    answers: list[dict | None] = []

    def bridge(path: str, method: str = "GET", body: dict | None = None, timeout: float = 1, base: str | None = None):
        assert base == "http://127.0.0.1:9"
        assert path == "/transcript"
        posts.append(body)
        return answers.pop(0) if answers else None

    monkeypatch.setattr(controller, "bridge_request", bridge)
    monkeypatch.setattr(controller, "resolve_delivery", lambda: (_ for _ in ()).throw(AssertionError("resolve_delivery")))

    mic = controller.MicState()
    mic.partial_base = "http://127.0.0.1:9"
    mic.partial_shown = "hello there"
    answers.append(None)
    mic.show_partial("good night")
    assert posts == [{"text": "scratch that"}]
    assert mic.partial_shown == "hello there"

    answers.append({"action": "appended"})
    mic.show_partial("good night")
    assert posts[-1] == {"text": "scratch that"}
    assert mic.partial_shown == "hello there"
    assert len(posts) == 2

    answers.extend([{"action": "scratched"}, {"action": "sent"}])
    mic.show_partial("good night")
    assert [post for post in posts[-2:]] == [{"text": "scratch that"}, {"text": "good night"}]
    assert mic.partial_shown == ""

    answers.append({"action": "appended"})
    mic.show_partial("good night")
    assert posts[-1] == {"text": "good night"}
    assert mic.partial_shown == "good night"

    mic.partial_shown = "good night"
    mic.partial_base = "http://127.0.0.1:9"
    answers.append({"action": "appended"})
    mic.retract_partial()
    assert posts[-1] == {"text": "scratch that"}
    assert mic.partial_shown == "good night"
    assert mic.partial_base == "http://127.0.0.1:9"


def test_ending_playback_drops_a_barge_hold_and_resumes_the_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    # resume_tts_clips sends SIGCONT. The held frames must not be sent to Whisper.
    import queue

    resumes = 0

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "resume_tts_clips", resume)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    for name in (
        "silence_speech",
        "kill_tts_clips",
        "pause_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "dispatch_transcript",
        "play_cue",
        "write_status",
        "stop_playback",
    ):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    class _Model:
        def predict(self, _frame: np.ndarray) -> dict[str, float]:
            return {"hey_jarvis": 0.0}

        def reset(self) -> None:
            return None

    def tick(mic: controller.MicState) -> queue.Queue:
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12
        mic.tts_active = False
        mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
        jobs: queue.Queue = queue.Queue(maxsize=1)
        frame = np.zeros(1280, dtype=np.int16)
        mic.handle_idle_frame(frame, 10.0, 0.0, 0.0, False, "test", _Model(), None, "hey_jarvis", 0.5, jobs)
        return jobs

    held = controller.MicState()
    held.tts_barge_held = True
    held.tts_barge_voice = True
    held.tts_stop_frames = [np.full(1280, 800, dtype=np.int16)]
    before = controller.time.monotonic()
    held_jobs = tick(held)
    assert resumes == 1
    assert held.tts_barge_held is False
    assert held.tts_barge_voice is False
    assert held.tts_stop_frames == []
    assert held.tts_floor_holdoff == 6
    assert held.tts_barge_cool_until >= before + 1.5
    assert held.whisper_pending is None
    assert held_jobs.empty()
    assert held.state == "IDLE"

    loose = controller.MicState()
    loose.tts_stop_frames = [np.full(1280, 800, dtype=np.int16)]
    loose_jobs = tick(loose)
    assert resumes == 1
    assert loose.tts_stop_frames == []
    assert loose.tts_barge_cool_until == 0.0
    assert loose_jobs.empty()


def test_two_quiet_frames_release_a_barge_hold_while_playback_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    # A hold that never becomes voice resumes the clip. resume_tts_clips sends SIGCONT.
    import queue

    resumes = 0

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "resume_tts_clips", resume)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    for name in (
        "silence_speech",
        "kill_tts_clips",
        "pause_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "dispatch_transcript",
        "play_cue",
        "write_status",
        "stop_playback",
    ):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    class _Model:
        def reset(self) -> None:
            return None

    def frame(mic: controller.MicState) -> queue.Queue:
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12
        mic.tts_active = True
        mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
        jobs: queue.Queue = queue.Queue(maxsize=1)
        mic.handle_idle_frame(
            np.zeros(1280, dtype=np.int16), 10.0, 0.0, 0.0, False, "MacBook Pro Speakers", _Model(), None, "hey_jarvis", 0.5, jobs
        )
        return jobs

    skipped = controller.MicState()
    skipped.tts_barge_held = True
    skipped.tts_barge_skip = 2
    skipped.tts_stop_frames = [np.full(1280, 800, dtype=np.int16)]
    frame(skipped)
    frame(skipped)
    assert resumes == 0
    assert skipped.tts_barge_held is True
    assert skipped.tts_barge_skip == 0
    assert skipped.tts_barge_quiet == 0
    assert len(skipped.tts_stop_frames) == 1

    held = controller.MicState()
    held.tts_barge_held = True
    held.tts_stop_frames = [np.full(1280, 800, dtype=np.int16), np.full(1280, 800, dtype=np.int16)]
    first = frame(held)
    assert resumes == 0
    assert held.tts_barge_held is True
    assert held.tts_barge_quiet == 1
    assert first.empty()
    second = frame(held)
    assert resumes == 0
    assert held.tts_barge_held is True
    assert held.tts_barge_waiting is True
    assert held.tts_stop_frames == []
    assert held.whisper_pending is not None
    assert held.whisper_pending["kind"] == "tts_barge"
    job = second.get_nowait()
    assert job["prompt"] == "Hey Jarvis. stop."
    assert held.tts_active is True
    assert held.state == "IDLE"


def test_an_unconfirmed_barge_does_not_resume_the_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty hold, a skipped Whisper job, and a rejected clip used to SIGCONT
    # the player. That restart is the echo. Only playback ending resumes it.
    import queue

    resumes = 0

    def resume() -> None:
        nonlocal resumes
        resumes += 1

    monkeypatch.setattr(controller, "resume_tts_clips", resume)
    monkeypatch.setattr(controller, "sync_speech_tier", lambda _now: None)
    monkeypatch.setattr(controller, "fn_held", lambda: False)
    monkeypatch.setattr(controller, "is_voicebox_speaking", lambda: False)
    for name in (
        "silence_speech",
        "kill_tts_clips",
        "pause_tts_clips",
        "handy_start_recording",
        "handy_cancel",
        "dispatch_transcript",
        "play_cue",
        "write_status",
        "stop_playback",
    ):
        monkeypatch.setattr(controller, name, lambda *_a, _name=name, **_k: (_ for _ in ()).throw(AssertionError(_name)))

    class _Model:
        def reset(self) -> None:
            return None

    def frame(mic: controller.MicState) -> queue.Queue:
        mic.last_manual_check = 1e12
        mic.last_tts_check = 1e12
        mic.tts_active = True
        mic.enter_dictating = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("enter_dictating"))  # type: ignore[method-assign]
        jobs: queue.Queue = queue.Queue(maxsize=1)
        mic.handle_idle_frame(
            np.zeros(1280, dtype=np.int16), 10.0, 0.0, 0.0, False, "MacBook Pro Speakers", _Model(), None, "hey_jarvis", 0.5, jobs
        )
        return jobs

    empty = controller.MicState()
    empty.tts_barge_held = True
    empty.tts_barge_skip = 0
    empty.tts_barge_quiet = 3
    empty.tts_stop_frames = []
    frame(empty)
    assert resumes == 0
    assert empty.tts_barge_held is False
    assert empty.tts_barge_quiet == 0
    assert empty.tts_floor_holdoff == 5
    assert empty.tts_active is True

    rejected = controller.MicState()
    rejected.tts_barge_held = True
    rejected.tts_barge_voice = False
    rejected.tts_barge_skip = 0
    rejected.tts_barge_quiet = 2
    rejected.tts_stop_frames = [np.full(1280, 800, dtype=np.int16)]
    frame(rejected)
    assert resumes == 0
    assert rejected.tts_barge_held is False
    assert rejected.tts_barge_waiting is False
    assert rejected.tts_stop_frames == []
    assert rejected.whisper_pending is None
    assert rejected.tts_active is True

    skipped = controller.MicState()
    skipped.tts_barge_held = True
    skipped.tts_barge_voice = False
    skipped.tts_barge_skip = 0
    skipped.tts_barge_quiet = 2
    skipped.tts_barge_next = None
    skipped.tts_stop_frames = [np.full(1280, 800, dtype=np.int16), np.full(1280, 800, dtype=np.int16)]
    monkeypatch.setattr(controller.MicState, "kick_whisper", lambda *_a, **_k: False)
    frame(skipped)
    assert resumes == 0
    assert skipped.tts_barge_held is False
    assert skipped.tts_barge_waiting is False
    assert skipped.tts_stop_frames == []
    assert skipped.whisper_pending is None
    assert skipped.tts_active is True
