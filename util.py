"""General Utility Functions."""


def deep_get(target: dict, *args: str, default=None) -> Any:
    """
    Walk into a dict and return the specified deep value.

    Example usage:

        >>> thing = {'a': {'b': {'c': 'foo'} } }
        >>> deep_get(thing, ('a', 'b', 'c'), None)
        'foo'
        >>> deep_get(thing, ('a', 'b'), None)
        {'c': 'foo'}
        >>> deep_get(thing, ('a', 'd'), None)
        None

    :param target: The dict to walk into for the desired value.
    :param args: The list of keys to walk down through.
    :param default: What to return if the target has no value.
    :return: The value at the target deep key.
    """
    if not hasattr(target, 'get'):
        raise ValueError(f"Cannot call get on {target} ({type(target)})")

    current = target
    for arg in args:
        res = current.get(arg)
        if res is None:
            return default

        current = res

    return current
