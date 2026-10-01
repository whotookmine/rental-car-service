"""Response shapes for notifications.

There is no request shape here, and that absence is the point: nothing a caller
sends creates a notification. See `app/notifications/router.py`.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    message: str
    created_at: datetime

    # Both, deliberately. `is_read` is the question a client asks when deciding
    # whether to show a badge; `read_at` is the one a person asks when wondering
    # whether they ever saw something. `is_read` is a property on the model, not a
    # column -- one fact lives in one place.
    is_read: bool
    read_at: datetime | None = None
