"""
timeout_session.py - requests session with timeout adapter.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from typing import Optional, Any
from requests import PreparedRequest, Response, Session
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

    def send(self, request: PreparedRequest, *args, **kwargs: Any) -> Response:
        """Send, but with a timeout always set."""
        if kwargs["timeout"] is None:
            kwargs["timeout"] = self.default_timeout

        return super().send(request, *args, **kwargs)


def new_session(
    timeout: int = REQUEST_TIMEOUT, session: Optional[Session] = None
) -> Session:
    """
    Create a new requests.Session and override the default HTTPAdapter with a TimeoutAdapter.

    :param timeout: the timeout to set the TimeoutAdapter to, defaults to REQUEST_TIMEOUT
    :param session: the Session object to attach the Adapter to, defaults to a new session
    :return: The created Session
    """
    with Session() as session:
        session.headers['User-Agent'] = user_agent
        adapter = TimeoutAdapter(timeout)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
