"""Test legacy plugin that implements every callback."""


def plugin_start3(_: str):
    """plugin_load3 test function."""
    return 'test_all_callbacks'


def plugin_stop() -> None:
    """plugin_stop test function."""
    print('Stopping')


def plugin_prefs(parent, cmdr: str, is_beta: bool) -> None:
    """plugin_prefs test function."""
    print('parent_prefs')


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """prefs_changed test function."""
    print('prefs_changed')


def plugin_app(parent) -> None:
    """plugin_app test function."""
    print('plugin_app')


def journal_entry(*args) -> None:
    """journal_entry test function."""
    print(f'journal_entry: {args}')


def dashboard_entry(*args) -> None:
    """dashboard_entry test function."""
    print(f'dashboard_entry: {args}')


def cmdr_data(*args) -> None:
    """cmdr_data test function."""
    print(f'lieutenant_cmdr_data: {args}')

# Start of plugin specific events


def edsm_notify_system(reply) -> None:
    """edsm_notify_system test function."""
    print(f'edsm_notify_system: {reply}')


def inara_notify_location(event_data) -> None:
    """inara_notify_location test function."""
    print(f'inara_notify_location: {event_data}')


def inara_notify_ship(event_data) -> None:
    """inara_notify_ship test function."""
    print(f'inara_notify_ship: {event_data}')
