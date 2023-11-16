"""
text.py - Dealing with Text and Bytes.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

from gzip import compress

__all__ = ['gzip']


def gzip(data: str | bytes, max_size: int = 512, encoding='utf-8') -> tuple[bytes, bool]:
    """
    Compress the given data if the max size is greater than specified.

    The default was chosen somewhat arbitrarily, see eddn.py for some more careful
    work towards keeping the data almost always compressed

    :param data: The data to compress
    :param max_size: The max size of data, in bytes, defaults to 512
    :param encoding: The encoding to use if data is a str, defaults to 'utf-8'
    :return: the payload to send, and a bool indicating compression state
    """
    if isinstance(data, str):
        data = data.encode(encoding=encoding)

    if len(data) <= max_size:
        return data, False

    return compress(data), True
