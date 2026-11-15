# flake8: noqa
# mypy: ignore-errors
"""Test the events the Inara plugin queues for journal entries."""

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def inara():
    """Import plugins.inara with its UI and game-state dependencies mocked."""
    mocked = {
        name: MagicMock()
        for name in (
            "tkinter",
            "tkinter.ttk",
            "myNotebook",
            "plug",
            "companion",
            "monitor",
            "ttkHyperlinkLabel",
            "l10n",
            "killswitch",
            "EDMCLogging",
            "plugins.common_coreutils",
        )
    }
    with patch.dict(sys.modules, mocked):
        sys.modules.pop("plugins.inara", None)
        import plugins.inara as module

        yield module
        sys.modules.pop("plugins.inara", None)


def queued_power_events(inara, entry):
    """Run one journal entry through the plugin and return the setCommanderRankPower events it queued."""
    inara.killswitch.check_killswitch.return_value = (False, entry)
    inara.monitor.is_live_galaxy.return_value = True
    inara.config.get_int.return_value = 1  # inara_out
    queued = []
    state = {"FID": "F123", "Role": None, "Reputation": None, "Engineers": None, "ShipID": None}
    with (
        patch.object(inara, "credentials", return_value="api-key"),
        patch.object(inara, "this_format_common"),
        patch.object(inara, "new_add_event", side_effect=lambda name, ts, data, *a, **k: queued.append((name, data))),
    ):
        inara.this.newuser = False
        inara.this.newsession = False
        inara.journal_entry("Cmdr", False, "Sol", "", entry, state)
    return [data for name, data in queued if name == "setCommanderRankPower"]


def test_powerplay_leave_sends_rank_minus_one(inara):
    # Inara's API docs: "When player is leaving a power, just set a rankValue [-1] for this power."
    entry = {"event": "PowerplayLeave", "timestamp": "2026-10-31T16:05:37Z", "Power": "Edmund Mahon"}
    assert queued_power_events(inara, entry) == [{"powerName": "Edmund Mahon", "rankValue": -1}]
