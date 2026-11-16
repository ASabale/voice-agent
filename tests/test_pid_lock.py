"""The PID-file flock is the only thing serializing controller starts.

VA-OPS-001: the controller has no supervisor, and any future crash-recovery
unit (launchd KeepAlive, a second `start` while a daemon is alive) can only be
safe if a second process can never get past `_open_pid_lock` while the daemon
holds it, and can get past it the moment the daemon dies — even uncleanly.
The daemon holds the flock for its whole life (`cmd_start_bg` passes the locked
fd to the child via `pass_fds`); the kernel releases it when the holder exits.
"""

import argparse
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_lock", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)

HOLDER_CODE = (
    "import fcntl, sys, time\n"
    "handle = open(sys.argv[1], 'a+', encoding='utf-8')\n"
    "fcntl.flock(handle.fileno(), fcntl.LOCK_EX)\n"
    "time.sleep(30)\n"
)
INHERIT_CODE = (
    "import os, time\n"
    "handle = os.fdopen(int(os.environ['OMP_VOICE_PID_LOCK_FD']), 'a+')\n"
    "handle.flush()\n"
    "time.sleep(30)\n"
)

_ARGS = argparse.Namespace(
    wake_word="hey_jarvis",
    wake_threshold=0.5,
    pause_seconds=5.0,
    idle_timeout=15.0,
)


class _PointedState:
    """Point the controller's state paths at a temp directory for one test."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.saved = (controller.STATE_DIR, controller.PID_FILE, controller.LOG_FILE,
                      controller.START_SPAWN_WAIT_SECONDS)

    def __enter__(self) -> Path:
        controller.STATE_DIR = self.tmp
        controller.PID_FILE = self.tmp / "controller.pid"
        controller.LOG_FILE = self.tmp / "controller.log"
        controller.START_SPAWN_WAIT_SECONDS = 0
        return self.tmp

    def __exit__(self, *exc: object) -> None:
        controller.STATE_DIR, controller.PID_FILE, controller.LOG_FILE, \
            controller.START_SPAWN_WAIT_SECONDS = self.saved


def _hold_lock(pid_file: Path) -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-c", HOLDER_CODE, str(pid_file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if controller._open_pid_lock(block=False) is None:
            return proc
        time.sleep(0.05)
    proc.kill()
    proc.wait()
    raise AssertionError("holder subprocess never acquired the lock")


def _wait_for_release(pid_file: Path, released: bool, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        handle = controller._open_pid_lock(block=False)
        if handle is not None:
            handle.close()
            if released:
                return True
        else:
            if not released:
                return True
        time.sleep(0.05)
    return False


class _SpawnRecorder:
    """Record what `cmd_start_bg` would spawn without touching the microphone."""

    def __init__(self) -> None:
        self.argvs = []

    def Popen(self, cmd, **kwargs):  # noqa: N802 - mirrors subprocess.Popen
        self.argvs.append(cmd)

        class _Fake:
            pid = 999999

        return _Fake()


def test_a_second_start_refuses_while_the_daemon_holds_the_lock(tmp_path, capsys, monkeypatch):
    with _PointedState(tmp_path) as state:
        holder = _hold_lock(state / "controller.pid")
        recorder = _SpawnRecorder()
        monkeypatch.setattr(controller.subprocess, "Popen", recorder.Popen)
        try:
            assert controller.cmd_start_bg(_ARGS) == 0
            out = capsys.readouterr().out
            assert "already running" in out
            assert recorder.argvs == [], "a held lock must never spawn a second mic owner"
        finally:
            holder.kill()
            holder.wait()


def test_a_crashed_daemon_releases_the_lock_and_the_stale_pid_is_ignored(tmp_path, capsys, monkeypatch):
    """SIGKILL releases the flock at the kernel level; the stale pid in the
    file must not stop a restart (the `os.kill(pid, 0)` probe raises OSError)."""
    with _PointedState(tmp_path) as state:
        pid_file = state / "controller.pid"
        holder = _hold_lock(pid_file)
        holder.kill()
        holder.wait()
        assert _wait_for_release(pid_file, released=True), "kernel did not release the flock"
        pid_file.write_text(str(holder.pid), encoding="utf-8")  # stale, dead pid
        recorder = _SpawnRecorder()
        monkeypatch.setattr(controller.subprocess, "Popen", recorder.Popen)
        assert controller.cmd_start_bg(_ARGS) == 0
        out = capsys.readouterr().out
        assert "Started" in out
        assert len(recorder.argvs) == 1 and "run" in recorder.argvs[0]
        assert pid_file.exists()


def test_the_spawned_daemon_inherits_the_lock_so_starts_stay_serialized(tmp_path):
    """The daemon itself holds the flock via the inherited fd; while it lives,
    every probe must be refused, and once it dies the probe must succeed."""
    with _PointedState(tmp_path) as state:
        pid_file = state / "controller.pid"
        probe = controller._open_pid_lock(block=False)
        assert probe is not None
        child = subprocess.Popen(
            [sys.executable, "-c", INHERIT_CODE],
            pass_fds=(probe.fileno(),),
            env={**os.environ, "OMP_VOICE_PID_LOCK_FD": str(probe.fileno())},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        probe.close()
        try:
            assert _wait_for_release(pid_file, released=False), "child did not take over the lock"
            child.kill()
            child.wait()
            assert _wait_for_release(pid_file, released=True), "lock stuck after child death"
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()


def test_run_refuses_when_the_lock_is_held(tmp_path, capsys):
    """VA-OPS-002 precondition: a supervised (launchd) `run` must refuse, not
    hang, while another instance holds the lock. Reproduced first: the old
    blocking claim made a second `run` load the models and then wait forever
    on the flock (see .local/voice-agent/runs/VA-OPS-001b-repro.json)."""
    with _PointedState(tmp_path) as state:
        holder = _hold_lock(state / "controller.pid")
        try:
            assert controller.run_daemon() == 1, "run must exit non-zero while the lock is held"
            out = capsys.readouterr().out
            assert "already running" in out.lower()
            assert controller._open_pid_lock(block=False) is None, "refused run must not steal the lock"
        finally:
            holder.kill()
            holder.wait()


def test_cli_run_exits_nonzero_when_supervised_against_a_held_lock(tmp_path):
    """End-to-end CLI form of the same guard: launchd execs `run` directly, so
    the process exit code is what the supervisor sees."""
    with _PointedState(tmp_path) as state:
        holder = _hold_lock(state / "controller.pid")
        try:
            proc = subprocess.run(
                [sys.executable, str(_PATH), "run"],
                env={**os.environ, "OMP_VOICE_STATE_DIR": str(state)},
                capture_output=True,
                text=True,
                timeout=20,
            )
            assert proc.returncode == 1, f"expected refusal exit 1, got {proc.returncode}"
            assert "already running" in (proc.stdout + proc.stderr).lower()
        finally:
            holder.kill()
            holder.wait()


def test_run_claim_acquires_and_holds_when_free(tmp_path):
    with _PointedState(tmp_path) as state:
        handle = controller._claim_run_lock()
        assert handle is not None, "a free lock must be claimable for a supervised start"
        assert controller._open_pid_lock(block=False) is None, "the claim must be held, not a transient probe"
        handle.close()
        assert controller._open_pid_lock(block=False) is not None, "closing the handle releases the lock"


def test_stop_on_a_dead_pid_file_leaves_no_stale_state(tmp_path, capsys):
    with _PointedState(tmp_path) as state:
        pid_file = state / "controller.pid"
        pid_file.write_text("999999999", encoding="utf-8")
        assert controller.cmd_stop() == 0
        assert "not running" in capsys.readouterr().out.lower()
        assert not pid_file.exists()


def _stub(code: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", code],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_stop_reports_success_when_the_process_exits_on_sigterm(tmp_path, capsys):
    """VA-OPS-004 criterion 1: a cooperative daemon is stopped, reported, and
    its pid file removed."""
    with _PointedState(tmp_path) as state:
        pid_file = state / "controller.pid"
        proc = _stub("import time; time.sleep(30)")
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        try:
            assert controller.cmd_stop() == 0
            assert "Stopped" in capsys.readouterr().out
            assert not pid_file.exists()
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def test_stop_reports_failure_when_the_process_survives_sigterm(tmp_path, capsys):
    """VA-OPS-004 criterion 2: a SIGTERM-ignoring process must not be reported
    as stopped, and the pid file must survive so `status` still tells the truth.
    The sentinel wait matters: a SIGTERM landing before the handler is installed
    kills the stub with the default disposition and the test would pass vacuously."""
    with _PointedState(tmp_path) as state:
        pid_file = state / "controller.pid"
        ready = tmp_path / "handler-installed"
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import signal, time, sys\n"
             "signal.signal(signal.SIGTERM, lambda *a: None)\n"
             "open(sys.argv[1], 'w').write('ready')\n"
             "time.sleep(30)\n",
             str(ready)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5.0
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "stub never installed its SIGTERM handler"
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        try:
            assert controller.cmd_stop() == 1
            out = capsys.readouterr().out
            assert "still alive" in out.lower()
            assert pid_file.read_text(encoding="utf-8").strip() == str(proc.pid)
        finally:
            proc.kill()
            proc.wait()


def test_stop_reaps_a_terminated_child_instead_of_calling_it_alive(tmp_path, capsys):
    """VA-OPS-004 criterion 4: kill(pid, 0) succeeds on a zombie; the reap in
    _process_exited must classify a dead own-child as exited."""
    with _PointedState(tmp_path) as state:
        pid_file = state / "controller.pid"
        proc = _stub("import time; time.sleep(30)")
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        proc.terminate()
        time.sleep(0.3)  # dead but deliberately NOT yet reaped: poll() would reap it
        assert proc.returncode is None  # harness has not reaped the zombie yet
        assert controller.cmd_stop() == 0
        assert "Stopped" in capsys.readouterr().out
        assert not pid_file.exists()



