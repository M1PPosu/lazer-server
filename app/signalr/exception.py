from __future__ import annotations


class SignalRException(Exception):
    pass


class InvokeException(SignalRException):
    def __init__(self, message: str) -> None:
        self.message = message
