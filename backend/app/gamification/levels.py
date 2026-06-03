"""Level system — XP thresholds."""


def get_level(xp: int) -> int:
    """Calculate level from XP."""
    if xp < 100:
        return 1
    elif xp < 300:
        return 2
    elif xp < 700:
        return 3
    elif xp < 1500:
        return 4
    else:
        return 5


def xp_for_next_level(xp: int) -> int:
    """XP needed for next level."""
    thresholds = [100, 300, 700, 1500, 3000]
    for t in thresholds:
        if xp < t:
            return t - xp
    return 0
