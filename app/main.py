"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.auth.router import router as auth_router
from app.blackout_windows.router import router as blackout_windows_router
from app.bookings.router import router as bookings_router
from app.branch_distances.router import router as branch_distances_router
from app.branches.router import router as branches_router
from app.core.config import get_settings
from app.core.errors import validation_exception_handler
from app.health.router import router as health_router
from app.providers.router import router as providers_router
from app.reviews.router import router as reviews_router
from app.vehicle_classes.router import router as vehicle_classes_router
from app.vehicles.router import router as vehicles_router
from app.one_way_routes.router import router as one_way_routes_router
from app.quotations.router import router as quotations_router

# Read and validate configuration before the app object exists, so a missing or
# malformed environment variable stops startup loudly instead of surfacing as a
# 500 on the first request.
settings = get_settings()

app = FastAPI(
    title="Rental Car Service",
    description=(
        "A web API through which registered users reserve cars from rental car "
        "providers for a period of time, and afterwards rate the provider they "
        "rented from."
    ),
    version="0.1.0",
)

# Validation errors echo the offending value by default, which would put a
# rejected password in the response body.
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(providers_router)
app.include_router(branches_router)
app.include_router(branch_distances_router)
app.include_router(bookings_router)
app.include_router(reviews_router)
app.include_router(vehicle_classes_router)
app.include_router(vehicles_router)
app.include_router(one_way_routes_router)
app.include_router(quotations_router)
app.include_router(blackout_windows_router)
