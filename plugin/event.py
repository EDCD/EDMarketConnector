"""Events for use with manager.pys event system."""
import time
from typing import Any, Dict, Optional


class BaseEvent:
    """
    Base Event class.

    Intended to simply signify that something happened. If you want to pass data
    with your event, use one of the subclasses below.
    """

    def __init__(self, name: str, event_time: float = None) -> None:
        self.name = name
        if event_time is None:
            event_time = time.time()

        self.time = event_time


class BaseDataEvent(BaseEvent):
    """
    Base Data carrying event class.

    Same as BaseEvent but carries some data as well.
    """

    def __init__(self, name: str, data: Any = None, event_time: float = None) -> None:
        super().__init__(name, event_time=event_time)
        self.data = data


class DictDataEvent(BaseDataEvent):
    """Same as a data event, but promises data is a dict."""

    def __init__(self, name: str, data: dict[Any, Any], event_time: float) -> None:
        super().__init__(name, data=data, event_time=event_time)
        self.data: dict[Any, Any] = data

        self.get = self.data.get

    def __getitem__(self, name: str) -> Any:
        return self.data[name]


class JournalEvent(DictDataEvent):
    """Journal event."""

    def __init__(
        self, name: str, data: Dict[str, Any], event_time: float, cmdr: str, is_beta: bool,
        system: Optional[str], station: Optional[str], state: Dict[str, Any]
    ) -> None:

        self.data: dict[str, Any]  # Override the definition in BaseDataEvent to be more specific
        super().__init__(name, data=data, event_time=event_time)
        self.commander = cmdr
        self.is_beta = is_beta
        self.system = system
        self.station = station
        self.state = state

        self.get = self.data.get  # Ease of use wrapper

    @property
    def event_name(self) -> str:
        """Get the event name for the current event."""
        return self.data['event']
