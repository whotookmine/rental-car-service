"""The one place that imports every model.

Alembic's env.py imports this module and nothing else, so autogeneration sees
the full table set. When a later ticket adds a model, add its import here — an
import that looks unused is doing its job.
"""

from app.db.base_class import Base as Base  # noqa: F401

# Models are registered by importing them below, one per feature package:
#   from app.auth.models import User  # noqa: F401
#   from app.providers.models import Provider  # noqa: F401
#   from app.bookings.models import Booking  # noqa: F401
#   from app.reviews.models import Review  # noqa: F401
# There are no models yet (ticket 01 is scaffold only).
