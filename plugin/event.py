"""Events for use with manager.pys event system."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, Generic, Mapping, Optional, TypeVar

if TYPE_CHECKING:
    from companion import CAPIData


class EDMCPluginEvents:
    """Events EDMC currently uses to communicate with plugins."""

    STARTUP_UI = 'core.setup_ui'
    JOURNAL_ENTRY = 'core.journal_event'
    CQC_JOURNAL_ENTRY = 'core.cqc_journal_event'
    DASHBOARD_ENTRY = 'core.dashboard_event'
    CAPI_DATA = 'core.capi_data'
    EDMC_SHUTTING_DOWN = 'core.shutdown'

    PREFERENCES = 'core.setup_preferences_ui'
    PREFERNCES_CMDR_CHANGED = 'core.preferences_cmdr_changed'
    PREFERENCES_CLOSED = 'core.preferences_closed'

    def __init__(self) -> None:
        raise NotImplementedError('This is not to be instantiated.')


class BaseEvent:
    """
    Base Event class.

    Intended to simply signify that something happened. If you want to pass data
    with your event, use one of the subclasses below.
    """

    def __init__(self, name: str, event_time: Optional[float] = None) -> None:
        self.name = name
        if event_time is None:
            event_time = time.time()

        self.time = event_time


T = TypeVar('T')


class BaseDataEvent(BaseEvent, Generic[T]):
    """
    Base Data carrying event class.

    Same as BaseEvent but carries some data as well.
    """

    def __init__(self, name: str, data: T, event_time: float = None) -> None:
        super().__init__(name, event_time=event_time)
        self.data: T = data


class JournalEvent(BaseDataEvent[Mapping[str, Any]]):
    """Journal event."""

    def __init__(
        self, name: str, data: Mapping[str, Any], cmdr: str, is_beta: bool,
        system: Optional[str], station: Optional[str], state: Dict[str, Any], event_time: float = None
    ) -> None:

        super().__init__(name, data=data, event_time=event_time)
        self.commander = cmdr
        self.get = data.get

    @property
    def event_name(self) -> str:
        """Get the event name for the current event."""
        return self.data['event']


CAPIDataEvent = BaseDataEvent[CAPIData]


class DashboardEvent(BaseDataEvent[Mapping[str, Any]]):
    """Dashboard file changed."""

    def __init__(self, name: str, commander: str, data: Mapping[Any, Any], event_time: float = None) -> None:
        super().__init__(name, data, event_time=event_time)
        self.commander = commander
