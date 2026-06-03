from __future__ import annotations
import random
from result import Result, ok_result, err_result, AUTH_EXPIRED, RATE_LIMIT, NOT_FOUND, TRANSIENT


class FakeHTTPError(Exception):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"HTTP {status}")


def classify_error(exc: Exception) -> str:
    if isinstance(exc, FakeHTTPError):
        if exc.status in (401, 403):
            return AUTH_EXPIRED
        if exc.status == 429:
            return RATE_LIMIT
        if exc.status == 404:
            return NOT_FOUND
    return TRANSIENT


def _flaky_http_call(user_id: int):
    """Simulates a remote call that can fail in four ways."""
    roll = random.randint(0, 4)
    if roll == 1:
        raise FakeHTTPError(401)
    if roll == 2:
        raise FakeHTTPError(429)
    if roll == 3:
        raise FakeHTTPError(404)
    if roll == 4:
        raise FakeHTTPError(500)
    return {"id": user_id, "name": "Alice"}


def fetch_user(user_id: int) -> Result[dict]:
    try:
        data = _flaky_http_call(user_id)
        return ok_result(data)
    except Exception as exc:
        kind = classify_error(exc)
        return err_result(kind, str(exc))


if __name__ == "__main__":
    random.seed(0)
    for i in range(5):
        r = fetch_user(user_id=1)
        print(r)
