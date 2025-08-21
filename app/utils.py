from __future__ import annotations

from datetime import datetime


def unix_timestamp_to_windows(timestamp: int) -> int:
    """Convert a Unix timestamp to a Windows timestamp."""
    return (timestamp + 62135596800) * 10_000_000


def camel_to_snake(name: str) -> str:
    """Convert a camelCase string to snake_case."""
    result = []
    last_chr = ""
    for char in name:
        if char.isupper():
            if not last_chr.isupper() and result:
                result.append("_")
            result.append(char.lower())
        else:
            result.append(char)
        last_chr = char
    return "".join(result)


def snake_to_camel(name: str, use_abbr: bool = True) -> str:
    """Convert a snake_case string to camelCase."""
    if not name:
        return name

    parts = name.split("_")
    if not parts:
        return name

    # 常见缩写词列表
    abbreviations = {
        "id",
        "url",
        "api",
        "http",
        "https",
        "xml",
        "json",
        "css",
        "html",
        "sql",
        "db",
    }

    result = []
    for part in parts:
        if part.lower() in abbreviations and use_abbr:
            result.append(part.upper())
        else:
            if result:
                result.append(part.capitalize())
            else:
                result.append(part.lower())

    return "".join(result)


def snake_to_pascal(name: str, use_abbr: bool = True) -> str:
    """Convert a snake_case string to PascalCase."""
    if not name:
        return name

    parts = name.split("_")
    if not parts:
        return name

    # 常见缩写词列表
    abbreviations = {
        "id",
        "url",
        "api",
        "http",
        "https",
        "xml",
        "json",
        "css",
        "html",
        "sql",
        "db",
    }

    result = []
    for part in parts:
        if part.lower() in abbreviations and use_abbr:
            result.append(part.upper())
        else:
            result.append(part.capitalize())

    return "".join(result)


def are_adjacent_weeks(dt1: datetime, dt2: datetime) -> bool:
    y1, w1, _ = dt1.isocalendar()
    y2, w2, _ = dt2.isocalendar()

    # 按 (年, 周) 排序，保证 dt1 <= dt2
    if (y1, w1) > (y2, w2):
        y1, w1, y2, w2 = y2, w2, y1, w1

    # 同一年，周数相邻
    if y1 == y2 and w2 - w1 == 1:
        return True

    # 跨年，判断 y2 是否是下一年，且 w2 == 1，并且 w1 是 y1 的最后一周
    if y2 == y1 + 1 and w2 == 1:
        # 判断 y1 的最后一周是多少
        last_week_y1 = datetime(y1, 12, 28).isocalendar()[1]  # 12-28 保证在最后一周
        if w1 == last_week_y1:
            return True

    return False


def are_same_weeks(dt1: datetime, dt2: datetime) -> bool:
    return dt1.isocalendar()[:2] == dt2.isocalendar()[:2]


def truncate(text: str, limit: int = 100, ellipsis: str = "...") -> str:
    if len(text) > limit:
        return text[:limit] + ellipsis
    return text
