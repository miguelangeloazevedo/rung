"""Merging two CSV exports by a shared key (first try)."""


def merge(first, second, key):
    return [first[0]], {"first": [], "second": []}
