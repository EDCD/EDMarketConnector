"""Test that the event engine is working as expected."""
from typing import cast

from plugin.event import BaseEvent
from plugin.manager import LoadedPlugin, PluginManager

from .conftest import good_path


def test_fire_event(plugin_manager: PluginManager) -> None:
    """Test that firing an event works correctly from the manager."""
    p = plugin_manager.load_plugin(good_path / 'simple_with_callback')
    assert p is not None

    test_event = BaseEvent('core.journal_event')
    plugin_manager.fire_event(test_event)
    assert test_event in getattr(p.plugin, 'called')


def test_catchall_event(plugin_manager: PluginManager) -> None:
    """Test that an * event hook is correctly resolved."""
    loaded = plugin_manager.load_plugins(
        (good_path / 'simple_with_callback', good_path / 'simple_full_wildcard', good_path / 'simple_nonfull_wildcard')
    )

    assert all(x is not None for x in loaded)
    loaded = cast(list[LoadedPlugin], loaded)  # type: ignore

    test_event = BaseEvent('core.journal_event')
    plugin_manager.fire_event(test_event)

    # if called exists, assert that it has the expected content.
    assert all(test_event in getattr(p, 'called') if hasattr(p, 'called') else True for p in loaded)


def test_multiple_hooks(plugin_manager: PluginManager) -> None:
    """Test that a hook function with multiple defined callbacks works."""
    p = plugin_manager.load_plugin(good_path / 'multi_callback')
    assert p is not None

    test_journal = BaseEvent('core.journal_event')
    test_not_journal = BaseEvent('uncore.not_journal_event')

    p.fire_event(test_journal)
    assert len(getattr(p.plugin, 'called')) == 1
    p.fire_event(test_not_journal)
    assert len(getattr(p.plugin, 'called')) == 2

    assert test_journal in getattr(p.plugin, 'called')
    assert test_not_journal in getattr(p.plugin, 'called')