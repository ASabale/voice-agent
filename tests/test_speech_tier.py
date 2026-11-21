"""Controller log rotation."""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "bin" / "omp-voice-controller"
_loader = importlib.machinery.SourceFileLoader("omp_voice_controller_tier", str(_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
controller = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = controller
_spec.loader.exec_module(controller)


def test_a_large_log_keeps_one_backup(tmp_path) -> None:
    log = tmp_path / "controller.log"
    log.write_text("old-line\n", encoding="utf-8")
    assert controller.rotate_log(log, 4) is True
    assert not log.exists()
    assert (tmp_path / "controller.log.1").read_text(encoding="utf-8") == "old-line\n"
    log.write_text("next-line\n", encoding="utf-8")
    assert controller.rotate_log(log, 4) is True
    assert (tmp_path / "controller.log.1").read_text(encoding="utf-8") == "next-line\n"
    assert controller.rotate_log(log, 100) is False
    assert controller.rotate_log(tmp_path / "missing.log", 4) is False
