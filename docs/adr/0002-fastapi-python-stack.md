# FastAPI, SQLAlchemy, and Alembic as the Python stack

The brief requires a REST API tested through Postman and says nothing about language;
we chose Python, then FastAPI over Django REST Framework and Flask. FastAPI publishes an
OpenAPI document that imports directly into Postman as a collection, which satisfies the
usability requirement by construction, and Pydantic request schemas are a natural home
for the booking validation rules (date ordering, maximum rental length, no past-dated
creation, rating bounds) so that invalid requests are rejected before reaching a handler.

## Consequences

- Authentication is hand-wired rather than inherited. Django REST Framework would have
  supplied permission classes and an admin UI that provisions admin accounts outside the
  API for free; with FastAPI we implement both ourselves.
