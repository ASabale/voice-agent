"""The isolated-session helper must not hand back the user's bridge."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import isolated_session as iso


def test_user_port_is_refused() -> None:
    owned = iso.protected_ports({16590: 62283, 26348: 63609}, {16590})
    with pytest.raises(iso.ProtectedSession) as raised:
        iso.assert_port_allowed(62283, owned)
    assert raised.value.pid == 16590
    assert raised.value.port == 62283


def test_other_port_is_allowed() -> None:
    owned = iso.protected_ports({16590: 62283, 26348: 63609}, {16590})
    iso.assert_port_allowed(63609, owned)
    assert iso.test_bridge({16590: 62283, 26348: 63609}, {16590}) == 63609


def test_no_bridge_when_only_the_user_is_up() -> None:
    assert iso.test_bridge({16590: 62283}, {16590}) is None
