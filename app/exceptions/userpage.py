"""
用户页面相关的异常类
"""

from __future__ import annotations


class UserpageError(Exception):
    """用户页面处理错误基类"""

    def __init__(self, message: str, code: str = "userpage_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ContentTooLongError(UserpageError):
    """内容过长错误"""

    def __init__(self, current_length: int, max_length: int):
        message = f"Content too long. Maximum {max_length} characters allowed, got {current_length}."
        super().__init__(message, "content_too_long")
        self.current_length = current_length
        self.max_length = max_length


class ContentEmptyError(UserpageError):
    """内容为空错误"""

    def __init__(self):
        super().__init__("Content cannot be empty.", "content_empty")


class BBCodeValidationError(UserpageError):
    """BBCode验证错误"""

    def __init__(self, errors: list[str]):
        message = f"BBCode validation failed: {'; '.join(errors)}"
        super().__init__(message, "bbcode_validation_error")
        self.errors = errors


class ForbiddenTagError(UserpageError):
    """禁止标签错误"""

    def __init__(self, tag: str):
        message = f"Forbidden tag '{tag}' is not allowed."
        super().__init__(message, "forbidden_tag")
        self.tag = tag
