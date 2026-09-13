"""FastAPI application entry point."""

from fastapi import FastAPI

from app.core.config import get_settings
from app.health.router import router as health_router

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

app.include_router(health_router)
