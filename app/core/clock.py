"""The single source of "today" for this codebase.

No other module may compute the current date directly: `date.today()`,
`datetime.now().date()` and friends are off-limits everywhere else, because they
read the system clock's timezone rather than the configured business timezone
(BUSINESS_TIMEZONE, Asia/Bangkok). Every date rule — no past-dated bookings, the
active-booking window, whether a rental period has ended — must go through
`today()` so the whole service agrees on which day it is.
"""

from datetime import date, datetime

from app.core.config import get_settings


def today() -> date:
    """Return the current date in the configured business timezone."""
    return datetime.now(tz=get_settings().business_tzinfo).date()
