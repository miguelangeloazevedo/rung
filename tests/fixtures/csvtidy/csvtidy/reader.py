"""Reading CSV text with an unknown delimiter."""

CANDIDATES = [",", ";", "\t", "|"]


def sniff(lines, sample=20):
    """Return the delimiter that splits the first lines into the most stable column count."""
    sample_lines = [line for line in lines[:sample] if line.strip()]
    if not sample_lines:
        return ","
    best, best_score = ",", -1
    for d in CANDIDATES:
        counts = [line.count(d) for line in sample_lines]
        if not counts or counts[0] == 0:
            continue
        stable = sum(1 for c in counts if c == counts[0])
        score = stable * 100 + counts[0]
        if score > best_score:
            best, best_score = d, score
    return best


def read_rows(text):
    lines = text.splitlines()
    d = sniff(lines)
    return [line.split(d) for line in lines if line.strip()]
