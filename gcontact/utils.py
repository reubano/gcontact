# -*- coding: utf-8 -*-

"""
gcontact.utils
~~~~~~~~~~~~~

This module contains utility functions.

"""

import re

from exceptions import NoValidUrlKeyFound

URL_KEY_V1_RE = re.compile(r'key=([^&#]+)')
URL_KEY_V2_RE = re.compile(r'/contacts/d/([a-zA-Z0-9-_]+)')


def finditem(func, seq):
    """Finds and returns first item in iterable for which func(item) is True.

    """
    return next((item for item in seq if func(item)))


def extract_id_from_url(url):
    m2 = URL_KEY_V2_RE.search(url)
    if m2:
        return m2.group(1)

    m1 = URL_KEY_V1_RE.search(url)
    if m1:
        return m1.group(1)

    raise NoValidUrlKeyFound


if __name__ == '__main__':
    import doctest
    doctest.testmod()
