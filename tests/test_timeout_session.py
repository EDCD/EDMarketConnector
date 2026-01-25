# flake8: noqa
# mypy: ignore-errors
"""Test timeout session system."""

from unittest.mock import MagicMock, patch
from requests import Session
import timeout_session


class TestTimeoutSession:

    def test_adapter_injects_default_timeout(self):
        """Verify the adapter sets the timeout if none is provided in the send call."""
        adapter = timeout_session.TimeoutAdapter(timeout=42)

        # We mock the parent HTTPAdapter.send method
        with patch("requests.adapters.HTTPAdapter.send") as mock_send:
            # Call send with timeout=None (which is what requests does by default)
            adapter.send(MagicMock(), timeout=None)

            # Check that the kwargs passed to super().send now contains our default
            args, kwargs = mock_send.call_args
            assert kwargs["timeout"] == 42

    def test_adapter_respects_explicit_timeout(self):
        """Verify the adapter doesn't override a timeout if the user explicitly provided one."""
        adapter = timeout_session.TimeoutAdapter(timeout=42)

        with patch("requests.adapters.HTTPAdapter.send") as mock_send:
            # User explicitly wants 5 seconds
            adapter.send(MagicMock(), timeout=5)

            args, kwargs = mock_send.call_args
            assert kwargs["timeout"] == 5

    def test_new_session_configuration(self):
        """Verify that new_session correctly mounts the adapter and sets headers."""
        custom_timeout = 15
        session = timeout_session.new_session(timeout=custom_timeout)

        # Check User-Agent
        assert "User-Agent" in session.headers

        # Check mounting
        # Prefix 'https://' should be mapped to our TimeoutAdapter
        adapter = session.adapters.get("https://")
        assert isinstance(adapter, timeout_session.TimeoutAdapter)
        assert adapter.default_timeout == custom_timeout

    def test_new_session_with_existing_object(self):
        """Verify new_session can wrap an existing Session object."""
        existing_session = Session()
        existing_session.headers["X-Test"] = "Existing"

        wrapped_session = timeout_session.new_session(session=existing_session)

        assert wrapped_session.headers["X-Test"] == "Existing"
        assert isinstance(
            wrapped_session.adapters.get("http://"), timeout_session.TimeoutAdapter
        )
