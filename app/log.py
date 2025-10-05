import http
import inspect
import logging
import re
from sys import stdout
from types import FunctionType
from typing import TYPE_CHECKING

from app.config import settings
from app.utils import snake_to_pascal

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
        _logger = logger
        if record.name == "uvicorn.access":
            message = self._format_uvicorn_access_log(message)
            color = True
            _logger = uvicorn_logger()
        elif record.name == "uvicorn.error":
            message = self._format_uvicorn_error_log(message)
            _logger = uvicorn_logger()
            color = True
        else:
            color = False
        _logger.opt(depth=depth, exception=record.exc_info, colors=color).log(level, message)

    def _format_uvicorn_error_log(self, message: str) -> str:
        websocket_pattern = r'(\d+\.\d+\.\d+\.\d+:\d+)\s*-\s*"WebSocket\s+([^"]+)"\s+([\w\[\]]+)'
        websocket_match = re.search(websocket_pattern, message)

        if websocket_match:
            ip, path, status = websocket_match.groups()

            colored_ip = f"<cyan>{ip}</cyan>"
            status_colors = {
                "[accepted]": "<green>[accepted]</green>",
                "403": "<red>403 [rejected]</red>",
            }
            colored_status = status_colors.get(status.lower(), f"<white>{status}</white>")
            return f'{colored_ip} - "<bold><magenta>WebSocket</magenta> {path}</bold>" {colored_status}'
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
            elif 400 <= status < 500 or 500 <= status < 600:
                status_color = "red"

            return (
                f'{colored_ip} - "<bold>{colored_method} '
                f'{path}</bold>" '
                f"<{status_color}>{status_code} {status_phrase}</{status_color}>"
            )

        return message


def get_caller_class_name(module_prefix: str = "", just_last_part: bool = True) -> str | None:
    stack = inspect.stack()
    for frame_info in stack[2:]:
        module = frame_info.frame.f_globals.get("__name__", "")
        if module_prefix and not module.startswith(module_prefix):
            continue

        local_vars = frame_info.frame.f_locals
        # 实例方法
        if "self" in local_vars:
            return local_vars["self"].__class__.__name__
        # 类方法
        if "cls" in local_vars:
            return local_vars["cls"].__name__

        # 静态方法 / 普通函数 -> 尝试通过函数名匹配类
        func_name = frame_info.function
        for obj_name, obj in frame_info.frame.f_globals.items():
            if isinstance(obj, type):  # 遍历模块内类
                cls = obj
                attr = getattr(cls, func_name, None)
                if isinstance(attr, (staticmethod, classmethod, FunctionType)):
                    return cls.__name__

        # 如果没找到类，返回模块名
        if just_last_part:
            return module.rsplit(".", 1)[-1]
        return module
    return None


def service_logger(name: str) -> "Logger":
    return logger.bind(service=name)


def fetcher_logger(name: str) -> "Logger":
    return logger.bind(fetcher=name)


def task_logger(name: str) -> "Logger":
    return logger.bind(task=name)


def system_logger(name: str) -> "Logger":
    return logger.bind(system=name)


def uvicorn_logger() -> "Logger":
    return logger.bind(uvicorn="Uvicorn")


def log(name: str) -> "Logger":
    return logger.bind(real_name=name)


def dynamic_format(record):
    name = ""

    uvicorn = record["extra"].get("uvicorn")
    if uvicorn:
        name = f"<fg #228B22>{uvicorn}</fg #228B22>"

    service = record["extra"].get("service")
    if not service:
        service = get_caller_class_name("app.service")
    if service:
        name = f"<blue>{service}</blue>"

    fetcher = record["extra"].get("fetcher")
    if not fetcher:
        fetcher = get_caller_class_name("app.fetcher")
    if fetcher:
        name = f"<magenta>{fetcher}</magenta>"

    task = record["extra"].get("task")
    if not task:
        task = get_caller_class_name("app.tasks")
    if task:
        task = snake_to_pascal(task)
        name = f"<fg #FFD700>{task}</fg #FFD700>"

    system = record["extra"].get("system")
    if system:
        name = f"<red>{system}</red>"

    if name == "":
        real_name = record["extra"].get("real_name", "") or record["name"]
        name = f"<fg #FFC1C1>{real_name}</fg #FFC1C1>"

    format = f"<green>{{time:YYYY-MM-DD HH:mm:ss}}</green> [<level>{{level}}</level>] | {name} | {{message}}\n"
    if record["exception"]:
        format += "{exception}\n"
    return format


logger.remove()
logger.add(
    stdout,
    colorize=True,
    format=dynamic_format,
    level=settings.log_level,
    diagnose=settings.debug,
)
logger.add(
    "logs/{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    colorize=False,
    format=dynamic_format,
    level=settings.log_level,
    diagnose=settings.debug,
    encoding="utf8",
)
logging.basicConfig(handlers=[InterceptHandler()], level=settings.log_level, force=True)

uvicorn_loggers = [
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
]

for logger_name in uvicorn_loggers:
    _uvicorn_logger = logging.getLogger(logger_name)
    _uvicorn_logger.handlers = [InterceptHandler()]
    _uvicorn_logger.propagate = False

logging.getLogger("httpx").setLevel("WARNING")
logging.getLogger("apscheduler").setLevel("WARNING")
