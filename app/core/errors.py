"""Error handling that keeps credentials out of responses.

Pydantic reports the offending value alongside each validation error, which is
helpful everywhere except on a password: a rejected registration would otherwise
answer with the plaintext password in the response body, where it lands in logs,
proxies, and the reporter's terminal history. This handler redacts those values
and changes nothing else about the default error shape.
"""

from typing import Any

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

SENSITIVE_FIELDS = frozenset({"password"})
REDACTED = "[redacted]"


def _redact_value(value: Any) -> Any:
    """Redact sensitive keys inside an echoed request body."""
    if isinstance(value, dict):
        return {
            key: (REDACTED if key in SENSITIVE_FIELDS else _redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_error(error: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(error)
    location = tuple(str(part) for part in redacted.get("loc", ()))

    if SENSITIVE_FIELDS.intersection(location):
        # The error is about the password itself; the value is never useful.
        redacted.pop("input", None)
        redacted.pop("ctx", None)
    elif "input" in redacted:
        # The error is about some other field, but the echoed body may still
        # carry a password alongside it.
        redacted["input"] = _redact_value(redacted["input"])

    return redacted


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder([_redact_error(e) for e in exc.errors()])},
    )
