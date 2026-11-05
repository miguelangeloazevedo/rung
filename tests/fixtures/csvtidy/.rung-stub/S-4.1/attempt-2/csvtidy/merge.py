"""Merging two CSV exports by a shared key."""


def merge(first, second, key):
    """Join rows of `second` onto `first` by the `key` column. Keeps the first file's order."""
    ka, kb = first[0].index(key), second[0].index(key)
    index = {row[kb]: row for row in second[1:]}
    extra = [c for i, c in enumerate(second[0]) if i != kb]
    out = [list(first[0]) + extra]
    seen = set()
    for row in first[1:]:
        match = index.get(row[ka])
        if match is not None:
            seen.add(row[ka])
            out.append(list(row) + [c for i, c in enumerate(match) if i != kb])
    unmatched = {
        "first": [row[ka] for row in first[1:] if row[ka] not in index],
        "second": [row[kb] for row in second[1:] if row[kb] not in seen],
    }
    return out, unmatched
