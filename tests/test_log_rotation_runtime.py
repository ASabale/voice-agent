"""A running controller daemon must rotate its own log, not only at start.

Evidence for the failure: `rotate_log` had exactly one call site, in the
`start` command before spawning, so `controller.log` reached 29.6 MB after one
day of a daemon that never restarted. These tests point fd 1 at a temp log
file and exercise the daemon condition directly.
"""

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_rotation", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def _run_with_stdout_as(fd: int, fn) -> None:
    original = os.dup(1)
    try:
        os.dup2(fd, 1)
        fn()
    finally:
        os.dup2(original, 1)
        os.close(original)
        os.close(fd)


def test_a_running_daemon_rotates_its_own_stdout_log(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "controller.log"
    monkeypatch.setattr(controller, "LOG_FILE", log_file)
    monkeypatch.setattr(controller, "LOG_ROTATE_BYTES", 200)
    log_file.write_bytes(b"x" * 300 + b"\n")

    fd = os.open(str(log_file), os.O_WRONLY | os.O_APPEND)

    def body() -> None:
        assert controller._rotate_stdout_log() is True
        # The old content moved to .1; a fresh, empty log is now open.
        assert log_file.stat().st_size == 0
        assert (tmp_path / "controller.log.1").stat().st_size == 301
        # The daemon's print lands on fd 1; pytest's sys.stdout replacement
        # does not, so verify at the fd level.
        os.write(1, b"after rotation\n")
        backup = (tmp_path / "controller.log.1").read_text(encoding="utf-8")
        fresh = log_file.read_text(encoding="utf-8")
        assert backup.startswith("x" * 300)
        assert "after rotation" in fresh
        # fd 1 must now write to the fresh file, not the backup.
        assert os.fstat(1).st_size == len(fresh)

    _run_with_stdout_as(fd, body)


def test_rotation_keeps_one_backup_and_rotates_again(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "controller.log"
    monkeypatch.setattr(controller, "LOG_FILE", log_file)
    monkeypatch.setattr(controller, "LOG_ROTATE_BYTES", 200)
    log_file.write_bytes(b"a" * 300 + b"\n")
    fd = os.open(str(log_file), os.O_WRONLY | os.O_APPEND)

    def body() -> None:
        assert controller._rotate_stdout_log() is True
        log_file.write_bytes(b"b" * 300 + b"\n")
        assert controller._rotate_stdout_log() is True
        assert (tmp_path / "controller.log.1").read_text(encoding="utf-8").startswith("b" * 300)
        assert not (tmp_path / "controller.log.2").exists()

    _run_with_stdout_as(fd, body)


def test_stdout_redirected_to_another_file_rotates_that_file(tmp_path, monkeypatch) -> None:
    """The live daemon (PID 90992) has stdout redirected to
    controller-restart.log, not controller.log. Under the old LOG_FILE-only
    guard that file grew unrotated past the limit. Rotation must follow the
    file fd 1 actually writes to, and leave the never-opened LOG_FILE alone."""
    log_file = tmp_path / "controller.log"
    other = tmp_path / "controller-restart.log"
    monkeypatch.setattr(controller, "LOG_FILE", log_file)
    monkeypatch.setattr(controller, "LOG_ROTATE_BYTES", 200)
    log_file.write_text("target untouched\n", encoding="utf-8")
    other.write_bytes(b"y" * 300)  # fd 1 is a regular file over the limit, but not LOG_FILE

    fd = os.open(str(other), os.O_WRONLY | os.O_APPEND)

    def body() -> None:
        assert controller._rotate_stdout_log() is True
        assert log_file.read_text(encoding="utf-8") == "target untouched\n"
        assert (tmp_path / "controller-restart.log.1").read_bytes().startswith(b"y" * 300)
        assert other.stat().st_size == 0
        os.write(1, b"fresh line\n")
        assert other.read_text(encoding="utf-8") == "fresh line\n"
        assert os.fstat(1).st_size == len("fresh line\n")

    _run_with_stdout_as(fd, body)


def test_deleted_stdout_file_is_never_rotated(tmp_path, monkeypatch) -> None:
    """An operator can rm the redirect file while the daemon holds it open.
    The fd stays a regular file over the limit, but there is no path to
    rotate; the guard must refuse rather than recreate a file at the old
    name. macOS lsof still reports the original path for the unlinked fd,
    so the `path.exists()` check is what refuses the rotation."""
    monkeypatch.setattr(controller, "LOG_ROTATE_BYTES", 200)
    gone = tmp_path / "gone.log"
    fd = os.open(str(gone), os.O_WRONLY | os.O_APPEND | os.O_CREAT)
    os.write(fd, b"z" * 300)
    gone.unlink()

    def body() -> None:
        assert controller._rotate_stdout_log() is False
        assert not gone.exists()
        assert not (tmp_path / "gone.log.1").exists()
        assert not (tmp_path / "gone.log (deleted)").exists()

    _run_with_stdout_as(fd, body)


def test_pipe_stdout_is_never_rotated(tmp_path, monkeypatch) -> None:
    """A daemon piped through tee must not have its pipe fd rotated."""
    monkeypatch.setattr(controller, "LOG_ROTATE_BYTES", 200)
    read_fd, write_fd = os.pipe()

    def body() -> None:
        assert controller._rotate_stdout_log() is False

    _run_with_stdout_as(write_fd, body)
    os.close(read_fd)


def test_under_limit_stdout_is_not_rotated(tmp_path, monkeypatch) -> None:
    log_file = tmp_path / "controller.log"
    monkeypatch.setattr(controller, "LOG_FILE", log_file)
    monkeypatch.setattr(controller, "LOG_ROTATE_BYTES", 1_048_576)
    log_file.write_bytes(b"z" * 100)

    fd = os.open(str(log_file), os.O_WRONLY | os.O_APPEND)

    def body() -> None:
        assert controller._rotate_stdout_log() is False
        assert log_file.exists()

    _run_with_stdout_as(fd, body)
