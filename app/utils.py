from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
import functools
import inspect
from io import BytesIO
from typing import Any, ParamSpec, TypeVar

from fastapi import HTTPException
from PIL import Image


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


def check_image(content: bytes, size: int, width: int, height: int) -> None:
    if len(content) > size:  # 10MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    elif len(content) == 0:
        raise HTTPException(status_code=400, detail="File cannot be empty")
    try:
        with Image.open(BytesIO(content)) as img:
            if img.format not in ["PNG", "JPEG", "GIF"]:
                raise HTTPException(status_code=400, detail="Invalid image format")
            if img.size[0] > width or img.size[1] > height:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image size exceeds {width}x{height} pixels",
                )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing image: {e}")


def simplify_user_agent(user_agent: str | None, max_length: int = 200) -> str | None:
    """
    简化 User-Agent 字符串，只保留 osu! 和关键设备系统信息浏览器

    Args:
        user_agent: 原始 User-Agent 字符串
        max_length: 最大长度限制

    Returns:
        简化后的 User-Agent 字符串，或 None
    """
    import re

    if not user_agent:
        return None

    # 如果长度在限制内，直接返回
    if len(user_agent) <= max_length:
        return user_agent

    # 提取操作系统信息
    os_info = ""
    os_patterns = [
        r"(Windows[^;)]*)",
        r"(Mac OS[^;)]*)",
        r"(Linux[^;)]*)",
        r"(Android[^;)]*)",
        r"(iOS[^;)]*)",
        r"(iPhone[^;)]*)",
        r"(iPad[^;)]*)",
    ]

    for pattern in os_patterns:
        match = re.search(pattern, user_agent, re.IGNORECASE)
        if match:
            os_info = match.group(1).strip()
            break

    # 提取浏览器信息
    browser_info = ""
    browser_patterns = [
        r"(osu![^)]*)",  # osu! 客户端
        r"(Chrome/[\d.]+)",
        r"(Firefox/[\d.]+)",
        r"(Safari/[\d.]+)",
        r"(Edge/[\d.]+)",
        r"(Opera/[\d.]+)",
    ]

    for pattern in browser_patterns:
        match = re.search(pattern, user_agent, re.IGNORECASE)
        if match:
            browser_info = match.group(1).strip()
            # 如果找到了 osu! 客户端，优先使用
            if "osu!" in browser_info.lower():
                break

    # 构建简化的 User-Agent
    parts = []
    if os_info:
        parts.append(os_info)
    if browser_info:
        parts.append(browser_info)

    if parts:
        simplified = "; ".join(parts)
    else:
        # 如果没有识别到关键信息，截断原始字符串
        simplified = user_agent[: max_length - 3] + "..."

    # 确保不超过最大长度
    if len(simplified) > max_length:
        simplified = simplified[: max_length - 3] + "..."

    return simplified


# https://github.com/encode/starlette/blob/master/starlette/_utils.py
T = TypeVar("T")
AwaitableCallable = Callable[..., Awaitable[T]]


def is_async_callable(obj: Any) -> bool:
    while isinstance(obj, functools.partial):
        obj = obj.func

    return inspect.iscoroutinefunction(obj)


P = ParamSpec("P")


async def run_in_threadpool(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    func = functools.partial(func, *args, **kwargs)
    return await asyncio.get_event_loop().run_in_executor(None, func)


class BackgroundTasks:
    def __init__(self, tasks: Sequence[asyncio.Task] | None = None):
        self.tasks = set(tasks) if tasks else set()

    def add_task(self, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> None:
        if is_async_callable(func):
            coro = func(*args, **kwargs)
        else:
            coro = run_in_threadpool(func, *args, **kwargs)
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()


bg_tasks = BackgroundTasks()


def utcnow() -> datetime:
    return datetime.now(tz=UTC)
