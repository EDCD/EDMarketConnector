"""
timeout_session.py - requests session with timeout adapter.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
from __future__ import annotations

import warnings
from requests import Session, Response
from requests.adapters import HTTPAdapter
from config import user_agent

REQUEST_TIMEOUT = 10  # Kept for backwards compatibility


class TimeoutAdapter(HTTPAdapter):
    """DEPRECATED: An HTTP Adapter that enforces an overridable default timeout on HTTP requests."""

    def __init__(self, timeout: int, *args, **kwargs):
        warnings.warn(
            "TimeoutAdapter is deprecated and will be removed in a future release.",
            category=DeprecationWarning,
            stacklevel=2
        )
        self.default_timeout = timeout
        kwargs.pop("timeout", None)
        super().__init__(*args, **kwargs)

    def send(self, *args, **kwargs) -> Response:
        """Send, but with a timeout always set."""
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.default_timeout
        return super().send(*args, **kwargs)


def new_session(timeout: int = REQUEST_TIMEOUT, session: Session | None = None) -> Session:
    """DEPRECATED: Create a new requests.Session."""
    warnings.warn(
        "timeout_session.new_session() is deprecated and will be removed. "
        "Use requests.Session() directly and pass explicit timeouts to request methods.",
        category=DeprecationWarning,
        stacklevel=2
    )

    session = session or Session()
    session.headers.setdefault("User-Agent", user_agent)

    adapter = TimeoutAdapter(timeout)
    for prefix in ("http://", "https://"):
        session.mount(prefix, adapter)

    return session
