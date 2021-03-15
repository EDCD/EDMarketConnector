
import time
from typing import Any, Optional


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


class JournalEvent(BaseDataEvent):
    """Journal event."""
