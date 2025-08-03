from __future__ import annotations


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


def snake_to_camel(name: str, lower_case: bool = True, use_abbr: bool = True) -> str:
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
            if result or not lower_case:
                result.append(part.capitalize())
            else:
                result.append(part.lower())

    return "".join(result)
