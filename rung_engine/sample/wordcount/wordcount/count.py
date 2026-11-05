"""Words are runs of characters separated by any whitespace."""


def count_words(text: str) -> int:
    return len(text.split())
