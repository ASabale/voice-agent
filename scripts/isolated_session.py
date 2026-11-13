"""Pick an OMP bridge that is not the user's session.

`omp-voice-controller inject` and `barge-in` call the live delivery path.
`silence_speech` posts `/barge-in` to every bridge. Neither is safe while a
protected pid is busy. Callers post only to a port this module allows.
"""

from __future__ import annotations


class ProtectedSession(Exception):
    def __init__(self, port: int, pid: int) -> None:
        self.port = port
        self.pid = pid
        super().__init__(f"port {port} belongs to protected pid {pid}")


def protected_ports(registry: dict[int, int], protected_pids: set[int]) -> dict[int, int]:
    """Map port to pid for sessions that must not be posted to."""
    return {port: pid for pid, port in registry.items() if pid in protected_pids}


def assert_port_allowed(port: int, owned: dict[int, int]) -> None:
    pid = owned.get(port)
    if pid is not None:
        raise ProtectedSession(port, pid)


def test_bridge(registry: dict[int, int], protected_pids: set[int]) -> int | None:
    """Return one bridge whose pid is not protected, or None."""
    owned = protected_ports(registry, protected_pids)
    for pid, port in registry.items():
        if pid not in protected_pids and port not in owned:
            return port
    return None
