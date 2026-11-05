"""Command line entry point."""

import argparse
import sys

from .dates import normalise
from .reader import read_rows


def main(argv=None):
    ap = argparse.ArgumentParser(prog="csvtidy")
    ap.add_argument("path")
    ap.add_argument("--locale", default="en_US")
    ap.add_argument("--date-column", type=int, default=None)
    a = ap.parse_args(argv)
    with open(a.path, encoding="utf-8") as fh:
        rows = read_rows(fh.read())
    for row in rows:
        if a.date_column is not None and a.date_column < len(row):
            try:
                row[a.date_column] = normalise(row[a.date_column], a.locale)
            except ValueError:
                pass
        sys.stdout.write(",".join(row) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
