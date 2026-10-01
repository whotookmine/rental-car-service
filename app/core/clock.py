"""The single source of the current time for this codebase.

No other module may ask the clock directly: `date.today()`, `datetime.now()` and
friends are off-limits everywhere else, because they read the system clock's
timezone rather than the configured business timezone (BUSINESS_TIMEZONE,
Asia/Bangkok). Every date rule — no past-dated bookings, the active-booking
window, whether a rental period has ended — must go through `today()` so the whole
service agrees on which day it is.

Two helpers, for two different kinds of thing, and the distinction matters:

- **`today()` — a domain date.** Rental periods, blackout windows and every rule
  that compares against "now" are dates with no time component, because that is
  what the domain says: a rental has no pickup hour, and storing an instant would
  invite a timezone conversion to shift the day.
- **`now()` — an event instant.** When a notification was created, when it was
  read. These are not domain dates but records of a moment, and rounding them to a
  day would make two events in one afternoon indistinguishable and unorderable.

Picking the wrong one is a bug in both directions: a date where an instant belongs
loses ordering, and an instant where a date belongs reintroduces exactly the
timezone drift this module exists to prevent.

**One deliberate exception**, so that the rule above is not quietly untrue:
`create_access_token` in `app/auth/security.py` reads `datetime.now(tz=timezone.utc)`
directly. A JWT's `iat` and `exp` are defined by the standard as seconds since the
Unix epoch, so UTC is not a choice there but the specification; routing it through
the business timezone would yield the identical instant and only obscure why. Token
lifetime is not a domain rule and has no business day.
"""

from datetime import date, datetime

from app.core.config import get_settings


def today() -> date:
    """Return the current date in the configured business timezone."""
    return datetime.now(tz=get_settings().business_tzinfo).date()


def now() -> datetime:
    """Return the current instant, timezone-aware, in the business timezone.

    For recording *when something happened*, never for a domain date — use
    `today()` for anything a rule compares against a rental period.

    Timezone-aware on purpose. A naive datetime stored in a `timestamptz` column
    is interpreted as whatever the database session's timezone happens to be, and
    the value that comes back is then off by the offset for part of the data.
    """
    return datetime.now(tz=get_settings().business_tzinfo)
