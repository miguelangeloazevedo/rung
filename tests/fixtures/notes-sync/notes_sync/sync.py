"""Plan which notes to copy between two folders."""


def plan(left, right):
    """left and right map a note title to its text. Return titles to copy each way."""
    to_right = sorted(t for t, body in left.items() if right.get(t) != body and t not in right)
    to_left = sorted(t for t, body in right.items() if t not in left)
    return {"to_right": to_right, "to_left": to_left}
