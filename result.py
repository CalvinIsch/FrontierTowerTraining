from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

T = TypeVar("T")

AUTH_EXPIRED = "AUTH_EXPIRED"
RATE_LIMIT   = "RATE_LIMIT"
NOT_FOUND    = "NOT_FOUND"
VALIDATION   = "VALIDATION"
TRANSIENT    = "TRANSIENT"


@dataclass
class Result(Generic[T]):
    ok: bool
    value: Optional[T]
    error: Optional[str]
    error_kind: Optional[str]


def ok_result(value: T) -> Result[T]:
    return Result(ok=True, value=value, error=None, error_kind=None)


def err_result(kind: str, message: str) -> Result:
    return Result(ok=False, value=None, error=message, error_kind=kind)


if __name__ == "__main__":
    print(ok_result({"id": 42, "name": "Alice"}))
    print(err_result(RATE_LIMIT, "Too many requests — back off 60 s"))
