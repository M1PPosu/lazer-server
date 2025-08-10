from __future__ import annotations

import http
import inspect
import logging
import re
from sys import stdout
from typing import TYPE_CHECKING

from app.config import settings

import loguru

if TYPE_CHECKING:
    from loguru import Logger

logger: "Logger" = loguru.logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        message = record.getMessage()

        if record.name == "uvicorn.access":
            message = self._format_uvicorn_access_log(message)
        elif record.name == "uvicorn.error":
            message = self._format_uvicorn_error_log(message)
        logger.opt(depth=depth, exception=record.exc_info, colors=True).log(
            level, message
        )

    def _format_uvicorn_error_log(self, message: str) -> str:
        websocket_pattern = (
            r'(\d+\.\d+\.\d+\.\d+:\d+)\s*-\s*"WebSocket\s+([^"]+)"\s+([\w\[\]]+)'
        )
        websocket_match = re.search(websocket_pattern, message)

        if websocket_match:
            ip, path, status = websocket_match.groups()

            colored_ip = f"<cyan>{ip}</cyan>"
            status_colors = {
                "[accepted]": "<green>[accepted]</green>",
                "403": "<red>403 [rejected]</red>",
            }
            colored_status = status_colors.get(
                status.lower(), f"<white>{status}</white>"
            )
            return (
                f'{colored_ip} - "<bold><magenta>WebSocket</magenta> '
                f'{path}</bold>" '
                f"{colored_status}"
            )
        else:
            return message

    def _format_uvicorn_access_log(self, message: str) -> str:
        http_pattern = r'(\d+\.\d+\.\d+\.\d+:\d+)\s*-\s*"(\w+)\s+([^"]+)"\s+(\d+)'

        http_match = re.search(http_pattern, message)
        if http_match:
            ip, method, path, status_code = http_match.groups()
            try:
                status_phrase = http.HTTPStatus(int(status_code)).phrase
            except ValueError:
                status_phrase = ""

            colored_ip = f"<cyan>{ip}</cyan>"
            method_colors = {
                "GET": "<green>GET</green>",
                "POST": "<blue>POST</blue>",
                "PUT": "<yellow>PUT</yellow>",
                "DELETE": "<red>DELETE</red>",
                "PATCH": "<magenta>PATCH</magenta>",
                "OPTIONS": "<white>OPTIONS</white>",
                "HEAD": "<white>HEAD</white>",
            }
            colored_method = method_colors.get(method, f"<white>{method}</white>")
            status = int(status_code)
            status_color = "white"
            if 200 <= status < 300:
                status_color = "green"
            elif 300 <= status < 400:
                status_color = "yellow"
            elif 400 <= status < 500:
                status_color = "red"
            elif 500 <= status < 600:
                status_color = "red"

            return (
                f'{colored_ip} - "<bold>{colored_method} '
                f'{path}</bold>" '
                f"<{status_color}>{status_code} {status_phrase}</{status_color}>"
            )

        return message


logger.remove()
logger.add(
    stdout,
    colorize=True,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> [<level>{level}</level>] | {message}"
    ),
    level=settings.log_level,
    diagnose=settings.debug,
)
logging.basicConfig(handlers=[InterceptHandler()], level=settings.log_level, force=True)

uvicorn_loggers = [
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
]

for logger_name in uvicorn_loggers:
    uvicorn_logger = logging.getLogger(logger_name)
    uvicorn_logger.handlers = [InterceptHandler()]
    uvicorn_logger.propagate = False
