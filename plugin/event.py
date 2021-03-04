
import time


class Event:
    def __init__(self, name: str, event_time: None) -> None:
        self.name = ""
        self.time = time.time()

        if event_time is not None:
            self.time = event_time
