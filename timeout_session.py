"""A requests.session with a TimeoutAdapter."""
import requests
from requests.adapters import HTTPAdapter

from config import user_agent

REQUEST_TIMEOUT = 10  # reasonable timeout that all HTTP requests should use


class TimeoutAdapter(HTTPAdapter):
    """An HTTP Adapter that enforces an overridable default timeout on HTTP requests."""

    def __init__(self, timeout: int, *args, **kwargs):
        self.default_timeout = timeout
        if kwargs.get("timeout") is not None:
            del kwargs["timeout"]

        super().__init__(*args, **kwargs)

    def send(self, *args, **kwargs) -> requests.Response:
        """Send, but with a timeout always set."""
        if kwargs["timeout"] is None:
            kwargs["timeout"] = self.default_timeout

        return super().send(*args, **kwargs)


def new_session(
    timeout: int = REQUEST_TIMEOUT, session: requests.Session = None
) -> requests.Session:
    """
    Create a new requests.Session and override the default HTTPAdapter with a TimeoutAdapter.

    :param timeout: the timeout to set the TimeoutAdapter to, defaults to REQUEST_TIMEOUT
    :param session: the Session object to attach the Adapter to, defaults to a new session
    :return: The created Session
    """
    if session is None:
        session = requests.Session()
        session.headers["User-Agent"] = user_agent

    adapter = TimeoutAdapter(timeout)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
