from __future__ import annotations

from collections.abc import Callable
import inspect
import sys
from typing import Any, ForwardRef, cast

# https://github.com/pydantic/pydantic/blob/main/pydantic/v1/typing.py#L61-L75
if sys.version_info < (3, 12, 4):

    def evaluate_forwardref(type_: ForwardRef, globalns: Any, localns: Any) -> Any:
        return cast(Any, type_)._evaluate(globalns, localns, recursive_guard=set())
else:

    def evaluate_forwardref(type_: ForwardRef, globalns: Any, localns: Any) -> Any:
        return cast(Any, type_)._evaluate(
            globalns, localns, type_params=(), recursive_guard=set()
        )


def get_annotation(param: inspect.Parameter, globalns: dict[str, Any]) -> Any:
    annotation = param.annotation
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        try:
            annotation = evaluate_forwardref(annotation, globalns, globalns)
        except Exception:
            return inspect.Parameter.empty
    return annotation


def get_signature(call: Callable[..., Any]) -> inspect.Signature:
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_annotation(param, globalns),
        )
        for param in signature.parameters.values()
    ]
    return inspect.Signature(typed_params)
