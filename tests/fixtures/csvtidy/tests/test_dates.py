import pytest

from csvtidy.dates import normalise


def test_iso_passthrough():
    assert normalise("2026-03-04") == "2026-03-04"


def test_month_first():
    assert normalise("03/04/2026") == "2026-03-04"


def test_dotted():
    assert normalise("4.3.2026", "de_DE") == "2026-03-04"


def test_single_digits():
    assert normalise("3/4/2026") == "2026-03-04"


def test_bad_date():
    with pytest.raises(ValueError):
        normalise("yesterday")


def test_ambiguous_locale():
    assert normalise("03/04/2026", "en_GB") == "2026-04-03"
