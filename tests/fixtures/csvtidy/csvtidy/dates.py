"""Normalising dates to ISO 8601 (YYYY-MM-DD)."""

import re

DAY_FIRST = {"en_GB", "de_DE", "fr_FR", "nl_BE", "es_ES", "it_IT"}
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_SLASH = re.compile(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})$")


def normalise(value, locale="en_US"):
    value = value.strip()
    if _ISO.match(value):
        return value
    m = _SLASH.match(value)
    if not m:
        raise ValueError(f"not a date: {value!r}")
    a, b, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if locale in DAY_FIRST:
        day, month = a, b
    else:
        month, day = a, b
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError(f"not a date: {value!r}")
    return f"{year:04d}-{month:02d}-{day:02d}"
