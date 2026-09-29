def split_seconds(time_seconds: float | None, meters: float | None) -> float | None:
    if time_seconds is None or meters is None:
        return None
    if time_seconds <= 0 or meters <= 0:
        return None
    return time_seconds * 500.0 / meters


def format_split(seconds: float | None) -> str | None:
    if seconds is None or seconds < 0:
        return None
    tenths = round(seconds * 10)
    minutes, rest = divmod(tenths, 600)
    whole_seconds, tenth = divmod(rest, 10)
    return f"{minutes}:{whole_seconds:02d}.{tenth}"


def watts(time_seconds: float | None, meters: float | None) -> float | None:
    if time_seconds is None or meters is None:
        return None
    if time_seconds <= 0 or meters <= 0:
        return None
    pace = time_seconds / meters
    return 2.8 / pace**3


def parse_split(text: str) -> float:
    value = text.strip()
    if not value:
        raise ValueError(f"invalid split: {text}")
    if ":" in value:
        minutes_part, seconds_part = value.split(":", maxsplit=1)
        minutes = float(minutes_part)
        seconds = float(seconds_part)
        if minutes < 0 or seconds < 0 or seconds >= 60:
            raise ValueError(f"invalid split: {text}")
        return minutes * 60.0 + seconds
    seconds = float(value)
    if seconds < 0:
        raise ValueError(f"invalid split: {text}")
    return seconds
