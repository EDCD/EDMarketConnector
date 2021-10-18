"""Test legacy plugin."""


def plugin_start3(_: str) -> str:
    """Explodes on call."""
    raise ValueError('BANG!')
