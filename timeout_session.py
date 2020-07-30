
import requests
from requests.adapters import HTTPAdapter

REQUEST_TIMEOUT = 10  # reasonable timeout that all HTTP requests should use


class TimeoutAdapter(HTTPAdapter):
    """
    TimeoutAdapter is an HTTP Adapter that enforces an overridable default timeout on HTTP requests.
    """
    def __init__(self, timeout, *args, **kwargs):
        self.default_timeout = timeout
        if kwargs.get("timeout") is not None:
            del kwargs["timeout"]

        super().__init__(*args, **kwargs)

    def send(self, *args, **kwargs):
        if kwargs["timeout"] is None:
            kwargs["timeout"] = self.default_timeout

        super().send(*args, **kwargs)


def new_session(timeout: int = REQUEST_TIMEOUT, session: requests.Session = None) -> requests.Session:
    """
    new_session creates a new requests.Session and overrides the default HTTPAdapter with a TimeoutAdapter.

    :param timeout: the timeout to set the TimeoutAdapter to, defaults to REQUEST_TIMEOUT
    :param session: the Session object to attach the Adapter to, defaults to a new session
    :return: The created Session
    """
    if session is None:
        session = requests.Session()

    adapter = TimeoutAdapter(timeout)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
