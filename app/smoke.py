"""A status-code smoke run across the whole service.

Run it against a running app and a freshly seeded database:

    uv run uvicorn app.main:app --port 8000     # in another shell
    uv run python -m app.seed
    uv run python -m app.smoke

**This is not the automated test suite the project decided against.** There are no
unit tests here, nothing runs in CI, and nothing is mocked: this is one command
that calls the real API over HTTP and checks the status code of every answer. Its
purpose is to catch a break, not to demonstrate behaviour -- the demonstration is
ticket 22's Postman collection, which asserts on payloads and is what a reader is
shown. See `docs/SPEC.md`.

**Status codes only, on purpose.** Response shapes churn: a booking's request body
has gained three fields since the collection was first specified. A run that
asserted shapes would fail every time someone added a column, and a check that
cries wolf gets ignored. `201` stays `201` when a payload grows a field, so a
failure here is always a real one.

Nothing seeded is hardcoded. Providers, classes, branches and one-way routes are
discovered through the API, so ticket 47 rebuilding the fixture cannot silently
turn this into a run against ids that mean something else.

Exit codes: 0 all checks passed, 1 at least one failed, 2 the preconditions were
not met (usually: the database needs re-seeding).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import timedelta

from app.core.clock import today

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")

# The seeded accounts. Used read-mostly: the run registers its own users for
# anything that consumes a booking slot, so these stay usable for a live demo.
SEEDED = {
    "admin": ("admin@example.com", "admin1234"),
    "demo": ("demo@example.com", "demo1234"),
}


def d(offset: int) -> str:
    """A date `offset` days from today, as the API wants it.

    Through `today()` rather than `date.today()` for the same reason every other
    date in this codebase is: the service runs in a business timezone seven hours
    from UTC, and a smoke run that disagreed with the server about what day it is
    would fail the past-dated checks for part of every day.
    """
    return (today() + timedelta(days=offset)).isoformat()


class Precondition(Exception):
    """The database is not in a state this run can say anything useful about."""


class Smoke:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.passed = 0
        self.failed: list[str] = []
        self.skipped: list[str] = []
        # Set once the seeded demo user has logged in; `discover` needs it to find
        # the ended booking, which only its owner and an admin can see.
        self.demo_token = ""
        # Every booking this run creates, so it can put the database back. Without
        # this the run is single-use: the bookings it leaves behind occupy the
        # one-car class, and the next run's capacity check fails for a reason that
        # has nothing to do with the code.
        self.booked: list[int] = []


    # -- plumbing ---------------------------------------------------------

    def call(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        token: str | None = None,
    ) -> tuple[int, object]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, method=method)
        if data is not None:
            request.add_header("content-type", "application/json")
        if token:
            request.add_header("authorization", f"Bearer {token}")

        try:
            # A timeout rather than hanging: a request that blocks forever on a
            # row lock would otherwise leave the run wedged with no output.
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw) if raw else None
            except json.JSONDecodeError:
                return error.code, raw.decode(errors="replace")
        except urllib.error.URLError as error:
            raise Precondition(
                f"No app answering at {self.base_url} ({error.reason}). Start it with "
                "`uv run uvicorn app.main:app --port 8000`."
            ) from error

    def check(
        self,
        label: str,
        expected: int,
        method: str,
        path: str,
        body: dict | None = None,
        token: str | None = None,
    ) -> object:
        """Assert one status code. Returns the parsed body for the next call's sake."""
        status, payload = self.call(method, path, body, token)
        if status == expected:
            self.passed += 1
            print(f"  pass  {label}  [{status}]")
        else:
            self.failed.append(label)
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            print(f"  FAIL  {label}  expected {expected}, got {status}: {detail!r}")
        return payload

    def booking_check(
        self, label: str, expected: int, path: str, body: dict, token: str
    ) -> int | None:
        """A booking creation, remembering the id so teardown can undo it."""
        payload = self.check(label, expected, "POST", path, body, token)
        if isinstance(payload, dict) and "id" in payload:
            self.booked.append(payload["id"])
            return payload["id"]
        return None

    def skip(self, label: str, why: str) -> None:
        self.skipped.append(label)
        print(f"  skip  {label}  ({why})")

    def token_for(self, email: str, password: str) -> str:
        status, payload = self.call(
            "POST", "/auth/login", {"email": email, "password": password}
        )
        if status != 200 or not isinstance(payload, dict):
            raise Precondition(
                f"Cannot log in as {email} (got {status}). Run `uv run python -m app.seed`."
            )
        return payload["access_token"]

    def register(self, tag: str) -> tuple[str, str]:
        """A throwaway registered user. Returns (email, token).

        The run registers its own rather than borrowing `fresh@example.com`,
        because filling a user to the three-booking cap would leave the seeded
        account unusable for a demo immediately afterwards.
        """
        email = f"smoke-{tag}-{os.getpid()}@example.com"
        status, payload = self.call(
            "POST",
            "/auth/register",
            {
                "name": f"Smoke {tag}",
                "telephone": "081-000-0000",
                "email": email,
                "password": "smokepass1",
            },
        )
        if status != 201 or not isinstance(payload, dict):
            raise Precondition(f"Could not register a throwaway user (got {status}).")
        return email, payload["access_token"]


def discover(s: Smoke, admin: str, user: str) -> dict:
    """Find the fixture through the API instead of assuming its ids."""
    status, providers = s.call("GET", "/providers?include_retired=true", token=admin)
    if status != 200 or not isinstance(providers, list) or not providers:
        raise Precondition("No providers. Run `uv run python -m app.seed`.")

    active = [p for p in providers if not p["is_retired"]]
    retired = [p for p in providers if p["is_retired"]]
    if not active:
        raise Precondition("Every provider is retired; nothing is bookable.")

    found: dict = {"retired": retired[0]["id"] if retired else None}

    # Score every active provider and take the most capable one, rather than the
    # first that merely works. A provider needs a branch and a class with a car in
    # it to be bookable at all -- but a one-car class is what makes the capacity
    # rule reachable in two requests, and an enabled one-way route is what makes
    # the directional refusal reachable at all. Taking the first bookable provider
    # silently skipped both of those checks the first time this ran, which is
    # exactly the kind of quiet gap this script exists to stop.
    best: tuple | None = None
    for candidate in active:
        _, classes = s.call(
            "GET", f"/providers/{candidate['id']}/vehicle_classes", token=user
        )
        _, branches = s.call("GET", f"/providers/{candidate['id']}/branches", token=user)
        _, routes = s.call(
            "GET", f"/providers/{candidate['id']}/one_way_routes", token=user
        )
        if not isinstance(classes, list) or not isinstance(branches, list):
            continue
        stocked = [c for c in classes if c.get("vehicle_count", 0) >= 1]
        if not stocked or not branches:
            continue
        single = [c for c in stocked if c["vehicle_count"] == 1]
        routes = routes if isinstance(routes, list) else []
        score = (bool(routes), bool(single), len(branches), len(stocked))
        if best is None or score > best[0]:
            best = (score, candidate["id"], stocked, branches, single, routes)

    if best is None:
        raise Precondition(
            "No provider has both a branch and a vehicle class with a car in it. "
            "Run `uv run python -m app.seed`."
        )

    _, provider_id, stocked, branches, single, routes = best
    found["provider"] = provider_id
    # The roomiest class for the ordinary bookings, so the cap and scoping checks
    # are not themselves refused for capacity.
    found["class"] = max(stocked, key=lambda c: c["vehicle_count"])["id"]
    found["branches"] = [b["id"] for b in branches]
    found["single_car_class"] = single[0]["id"] if single else None
    found["one_way"] = routes[0] if routes else None

    # Another provider's class, for the cross-provider refusal.
    found["foreign_class"] = None
    for provider in active:
        if provider["id"] == found["provider"]:
            continue
        _, classes = s.call(
            "GET", f"/providers/{provider['id']}/vehicle_classes", token=user
        )
        if isinstance(classes, list) and classes:
            found["foreign_class"] = classes[0]["id"]
            break

    # The seeded ended booking, which is the only way to reach the two rules that
    # depend on a rental period having finished.
    _, bookings = s.call("GET", "/bookings", token=s.demo_token)
    ended = [b for b in bookings if b["end_date"] < today().isoformat()]
    upcoming = [b for b in bookings if b["end_date"] >= today().isoformat()]
    if not ended:
        raise Precondition(
            "The demo user holds no ended booking, so the reviewable-when-ended and "
            "ended-does-not-count rules cannot be reached. Run "
            "`uv run python -m app.seed`."
        )
    found["ended_booking"] = ended[0]["id"]
    found["upcoming_booking"] = upcoming[0]["id"] if upcoming else None
    return found


def main() -> int:
    s = Smoke(BASE_URL)
    print(f"Smoke run against {s.base_url}\n")

    try:
        status, _ = s.call("GET", "/health")
        if status != 200:
            raise Precondition(f"/health answered {status}; the app is not healthy.")

        admin = s.token_for(*SEEDED["admin"])
        s.demo_token = s.token_for(*SEEDED["demo"])
        demo = s.demo_token

        print("## authentication")
        email_a, user_a = s.register("a")
        s.check("register a new user", 201, "POST", "/auth/register",
                {"name": "Dup", "telephone": "081", "email": f"dup-{os.getpid()}@example.com",
                 "password": "smokepass1"})
        s.check("the same email again", 409, "POST", "/auth/register",
                {"name": "Dup", "telephone": "081", "email": f"dup-{os.getpid()}@example.com",
                 "password": "smokepass1"})
        s.check("the same email uppercased", 409, "POST", "/auth/register",
                {"name": "Dup", "telephone": "081",
                 "email": f"DUP-{os.getpid()}@EXAMPLE.COM", "password": "smokepass1"})
        s.check("password under eight characters", 422, "POST", "/auth/register",
                {"name": "X", "telephone": "081", "email": "short@example.com",
                 "password": "abc"})
        s.check("client asking for the admin role", 422, "POST", "/auth/register",
                {"name": "X", "telephone": "081", "email": "sneak@example.com",
                 "password": "smokepass1", "role": "admin"})
        s.check("registration without a telephone", 422, "POST", "/auth/register",
                {"name": "X", "email": "notel@example.com", "password": "smokepass1"})
        s.check("login with the right password", 200, "POST", "/auth/login",
                {"email": email_a, "password": "smokepass1"})
        s.check("login with the wrong password", 401, "POST", "/auth/login",
                {"email": email_a, "password": "wrongwrong"})
        s.check("login as an email that does not exist", 401, "POST", "/auth/login",
                {"email": "nobody@example.com", "password": "wrongwrong"})
        s.check("logout", 200, "POST", "/auth/logout", token=user_a)
        s.check("who am I", 200, "GET", "/auth/me", token=user_a)
        s.check("a protected route with no token", 401, "GET", "/bookings")
        s.check("a protected route with a garbage token", 401, "GET", "/bookings",
                token="garbage")

        fixture = discover(s, admin, user_a)
        provider = fixture["provider"]
        klass = fixture["class"]
        branch = fixture["branches"][0]
        print(f"\n(discovered provider {provider}, class {klass}, branch {branch})")

        def booking(start: int, end: int, **overrides) -> dict:
            body = {
                "vehicle_class_id": klass,
                "pickup_branch_id": branch,
                "start_date": d(start),
                "end_date": d(end),
            }
            body.update(overrides)
            return body

        print("\n## providers")
        s.check("list providers", 200, "GET", "/providers", token=user_a)
        s.check("fetch one provider", 200, "GET", f"/providers/{provider}", token=user_a)
        s.check("a provider that does not exist", 404, "GET", "/providers/99999999",
                token=user_a)
        s.check("a registered user creating a provider", 403, "POST", "/providers",
                {"name": "Nope", "address": "x", "telephone": "081"}, token=user_a)
        if fixture["retired"]:
            s.check("fetch a retired provider directly", 200, "GET",
                    f"/providers/{fixture['retired']}", token=user_a)
        else:
            s.skip("fetch a retired provider directly", "no retired provider in the fixture")

        print("\n## booking creation and its refusals")
        booking_a = s.booking_check("create a booking", 201,
                                    f"/providers/{provider}/bookings", booking(10, 12),
                                    user_a)
        s.booking_check("a single-day rental", 201, f"/providers/{provider}/bookings",
                        booking(10, 10), user_a)
        s.check("end date before start date", 422, "POST",
                f"/providers/{provider}/bookings", booking(12, 10), token=user_a)
        s.check("a start date in the past", 422, "POST",
                f"/providers/{provider}/bookings", booking(-5, 1), token=user_a)
        s.check("a rental period over thirty days", 422, "POST",
                f"/providers/{provider}/bookings", booking(10, 45), token=user_a)
        s.check("a provider that does not exist", 404, "POST",
                "/providers/99999999/bookings", booking(10, 12), token=user_a)
        s.check("a vehicle class that does not exist", 422, "POST",
                f"/providers/{provider}/bookings",
                booking(10, 12, vehicle_class_id=99999999), token=user_a)
        s.check("an over-large vehicle class id", 422, "POST",
                f"/providers/{provider}/bookings",
                booking(10, 12, vehicle_class_id=99999999999), token=user_a)
        s.check("an unexpected field in the body", 422, "POST",
                f"/providers/{provider}/bookings", booking(10, 12, surprise="x"),
                token=user_a)
        s.check("an admin holding a booking", 403, "POST",
                f"/providers/{provider}/bookings", booking(10, 12), token=admin)
        if fixture["foreign_class"]:
            s.check("another provider's vehicle class", 409, "POST",
                    f"/providers/{provider}/bookings",
                    booking(10, 12, vehicle_class_id=fixture["foreign_class"]),
                    token=user_a)
        else:
            s.skip("another provider's vehicle class", "only one provider has a catalogue")
        if fixture["retired"]:
            s.check("booking a retired provider", 409, "POST",
                    f"/providers/{fixture['retired']}/bookings", booking(10, 12),
                    token=user_a)
        else:
            s.skip("booking a retired provider", "no retired provider in the fixture")

        print("\n## the three-active cap")
        email_b, user_b = s.register("b")
        s.check("first active booking", 201, "POST", f"/providers/{provider}/bookings",
                booking(3, 4), token=user_b)
        s.check("second active booking", 201, "POST", f"/providers/{provider}/bookings",
                booking(5, 6), token=user_b)
        s.check("third active booking", 201, "POST", f"/providers/{provider}/bookings",
                booking(7, 8), token=user_b)
        s.check("the fourth is refused", 409, "POST", f"/providers/{provider}/bookings",
                booking(20, 21), token=user_b)
        # The seeded ended booking proves the other half of the rule: the demo user
        # holds it and is still able to book, so a finished rental has stopped
        # occupying a slot. Not reachable by API calls alone, which is why the
        # fixture carries a past-dated booking at all.
        s.booking_check("an ended booking does not count toward the cap", 201,
                        f"/providers/{provider}/bookings", booking(16, 17), demo)

        print("\n## capacity")
        if fixture["single_car_class"]:
            one_car = fixture["single_car_class"]
            email_c, user_c = s.register("c")
            s.booking_check("take the only car in a class", 201,
                            f"/providers/{provider}/bookings",
                            booking(25, 26, vehicle_class_id=one_car), user_c)
            s.check("the class is then full", 409, "POST",
                    f"/providers/{provider}/bookings",
                    booking(25, 26, vehicle_class_id=one_car), token=user_a)
        else:
            s.skip("a full vehicle class", "no class in the fixture has exactly one car")

        print("\n## one-way")
        if fixture["one_way"]:
            route = fixture["one_way"]
            # The read shape nests both ends rather than carrying bare ids.
            there, back = route["from_branch"]["id"], route["to_branch"]["id"]
            email_e, user_e = s.register("e")
            s.booking_check("the enabled one-way direction", 201,
                            f"/providers/{provider}/bookings",
                            booking(27, 28, pickup_branch_id=there,
                                    dropoff_branch_id=back), user_e)
            s.check("the unenabled reverse direction", 409, "POST",
                    f"/providers/{provider}/bookings",
                    booking(27, 28, pickup_branch_id=back, dropoff_branch_id=there),
                    token=user_e)
            s.booking_check("same branch at both ends is a round trip", 201,
                            f"/providers/{provider}/bookings",
                            booking(29, 30, pickup_branch_id=there,
                                    dropoff_branch_id=there), user_e)
        else:
            s.skip("one-way enablement", "no one-way route in the fixture")

        print("\n## viewing, ownership scoping, editing, deleting")
        s.check("my own bookings", 200, "GET", "/bookings", token=user_a)
        s.check("one of my own bookings", 200, "GET", f"/bookings/{booking_a}",
                token=user_a)
        s.check("a booking that does not exist", 404, "GET", "/bookings/99999999",
                token=user_a)
        s.check("another user's booking, fetched", 404, "GET", f"/bookings/{booking_a}",
                token=user_b)
        s.check("another user's booking, edited", 404, "PUT", f"/bookings/{booking_a}",
                {"start_date": d(11), "end_date": d(12)}, token=user_b)
        s.check("another user's booking, deleted", 404, "DELETE",
                f"/bookings/{booking_a}", token=user_b)
        s.check("re-date my own booking", 200, "PUT", f"/bookings/{booking_a}",
                {"start_date": d(11), "end_date": d(13)}, token=user_a)
        s.check("re-date with end before start", 422, "PUT", f"/bookings/{booking_a}",
                {"start_date": d(13), "end_date": d(11)}, token=user_a)
        s.check("re-dating may not move the provider", 422, "PUT",
                f"/bookings/{booking_a}",
                {"start_date": d(11), "end_date": d(13), "provider_id": provider},
                token=user_a)
        s.check("re-dating may not move the vehicle class", 422, "PUT",
                f"/bookings/{booking_a}",
                {"start_date": d(11), "end_date": d(13), "vehicle_class_id": klass},
                token=user_a)

        print("\n## admin oversight")
        s.check("admin sees every booking", 200, "GET", "/bookings", token=admin)
        s.check("admin fetches someone else's booking", 200, "GET",
                f"/bookings/{booking_a}", token=admin)
        s.check("admin re-dates someone else's booking", 200, "PUT",
                f"/bookings/{booking_a}", {"start_date": d(11), "end_date": d(12)},
                token=admin)
        s.check("admin is held to the same date rules", 422, "PUT",
                f"/bookings/{booking_a}", {"start_date": d(12), "end_date": d(11)},
                token=admin)

        print("\n## reviews")
        ended_booking = fixture["ended_booking"]
        if fixture["upcoming_booking"]:
            s.check("reviewing a rental that has not ended", 409, "POST",
                    f"/bookings/{fixture['upcoming_booking']}/reviews",
                    {"rating": 5, "comment": "too early"}, token=demo)
        else:
            s.skip("reviewing a rental that has not ended", "no upcoming booking")
        s.check("a rating below one", 422, "POST", f"/bookings/{ended_booking}/reviews",
                {"rating": 0, "comment": "x"}, token=demo)
        s.check("a rating above five", 422, "POST", f"/bookings/{ended_booking}/reviews",
                {"rating": 6, "comment": "x"}, token=demo)
        s.check("reviewing someone else's booking", 404, "POST",
                f"/bookings/{ended_booking}/reviews", {"rating": 5, "comment": "x"},
                token=user_a)

        status, payload = s.call("POST", f"/bookings/{ended_booking}/reviews",
                                 {"rating": 4, "comment": "Smoke run."}, token=demo)
        if status == 409:
            raise Precondition(
                "The seeded ended booking already carries a review, so the "
                "review-once and reviewable-when-ended rules cannot be checked. Run "
                "`uv run python -m app.seed`."
            )
        s.passed += 1 if status == 201 else 0
        if status != 201:
            s.failed.append("review an ended booking")
            print(f"  FAIL  review an ended booking  expected 201, got {status}")
        else:
            print(f"  pass  review an ended booking  [{status}]")
        review = payload["id"] if isinstance(payload, dict) else None

        s.check("a second review on one booking", 409, "POST",
                f"/bookings/{ended_booking}/reviews", {"rating": 2, "comment": "again"},
                token=demo)
        s.check("the author edits their review", 200, "PUT", f"/reviews/{review}",
                {"rating": 5, "comment": "Edited by the smoke run."}, token=demo)
        s.check("someone else edits that review", 404, "PUT", f"/reviews/{review}",
                {"rating": 1, "comment": "hijack"}, token=user_a)
        s.check("a review may not be moved to another booking", 422, "PUT",
                f"/reviews/{review}",
                {"rating": 5, "comment": "x", "booking_id": booking_a}, token=demo)
        s.check("a reviewed booking may not be re-dated forward", 409, "PUT",
                f"/bookings/{ended_booking}", {"start_date": d(2), "end_date": d(3)},
                token=demo)
        s.check("an admin may not re-date it either", 409, "PUT",
                f"/bookings/{ended_booking}", {"start_date": d(2), "end_date": d(3)},
                token=admin)
        s.check("a registered user deleting a review they did not write", 404, "DELETE",
                f"/reviews/{review}", token=user_a)
        s.check("an admin deletes an inappropriate review", 204, "DELETE",
                f"/reviews/{review}", token=admin)

        again = s.check("the booking is reviewable again", 201, "POST",
                        f"/bookings/{ended_booking}/reviews",
                        {"rating": 3, "comment": "Second pass."}, token=demo)
        # Put the fixture back: a demo should still be able to perform the first
        # review, and the provider's average should still read as untested.
        if isinstance(again, dict):
            s.check("clean up, leaving no reviews behind", 204, "DELETE",
                    f"/reviews/{again['id']}", token=admin)

        print("\n## maintenance blackout windows")
        # On a throwaway car of its own, so the seeded fleet keeps the capacity it
        # is documented as having and the RESTRICT check below can end by removing
        # the vehicle it made.
        made = s.check("add a throwaway vehicle", 201, "POST",
                       f"/vehicle_classes/{klass}/vehicles",
                       {"plate": f"SMOKE-{os.getpid()}"}, token=admin)
        vehicle = made["id"] if isinstance(made, dict) else None
        windows: list[int] = []

        def window(label: str, expected: int, start: int, end: int) -> None:
            payload = s.check(label, expected, "POST",
                              f"/vehicles/{vehicle}/blackout_windows",
                              {"start_date": d(start), "end_date": d(end)}, token=admin)
            if isinstance(payload, dict) and "id" in payload:
                windows.append(payload["id"])

        window("schedule a blackout window", 201, 40, 44)
        window("a single-day window", 201, 50, 50)
        window("end date before start date", 422, 44, 40)
        window("an overlapping window", 409, 42, 46)
        window("one wholly inside it", 409, 41, 43)
        # The boundary, stated in docs/SPEC.md: inclusive at both ends, so a window
        # ending the day before another starts is adjacent, not overlapping.
        window("an adjacent window ending the day before", 201, 38, 39)
        window("an adjacent window starting the day after", 201, 45, 46)
        s.check("a window in the past", 201, "POST",
                f"/vehicles/{vehicle}/blackout_windows",
                {"start_date": d(-30), "end_date": d(-25)}, token=admin)
        s.check("an unexpected field on a window", 422, "POST",
                f"/vehicles/{vehicle}/blackout_windows",
                {"start_date": d(60), "end_date": d(61), "reason": "oil"}, token=admin)
        s.check("a registered user reading windows", 200, "GET",
                f"/vehicles/{vehicle}/blackout_windows", token=user_a)
        s.check("anonymous reading windows", 401, "GET",
                f"/vehicles/{vehicle}/blackout_windows")
        s.check("a registered user scheduling one", 403, "POST",
                f"/vehicles/{vehicle}/blackout_windows",
                {"start_date": d(70), "end_date": d(71)}, token=user_a)
        s.check("a window on a vehicle that does not exist", 404, "POST",
                "/vehicles/99999999/blackout_windows",
                {"start_date": d(70), "end_date": d(71)}, token=admin)
        if windows:
            s.check("re-date a window", 200, "PUT", f"/blackout_windows/{windows[0]}",
                    {"start_date": d(40), "end_date": d(43)}, token=admin)
            s.check("a window may not move to another vehicle", 422, "PUT",
                    f"/blackout_windows/{windows[0]}",
                    {"start_date": d(40), "end_date": d(43), "vehicle_id": vehicle},
                    token=admin)
            s.check("a registered user re-dating one", 403, "PUT",
                    f"/blackout_windows/{windows[0]}",
                    {"start_date": d(40), "end_date": d(43)}, token=user_a)
        # Ticket 40: a car in the workshop leaves availability. The throwaway
        # vehicle above is in `klass`, so its windows move that class's count.
        def free_count(start: int, end: int) -> int | None:
            _, rows = s.call(
                "GET",
                f"/providers/{provider}/availability"
                f"?start_date={d(start)}&end_date={d(end)}",
                token=user_a,
            )
            if not isinstance(rows, list):
                return None
            for row in rows:
                if row["vehicle_class_id"] == klass:
                    return row["free_count"]
            return None

        s.check("availability over a clear range", 200, "GET",
                f"/providers/{provider}/availability"
                f"?start_date={d(90)}&end_date={d(91)}", token=user_a)
        clear = free_count(90, 91)
        # A window over that range must cost the class exactly one car, and a
        # window ending the day before must cost it none. Compared against the
        # count just measured rather than against a hardcoded number, so the
        # check survives ticket 47 rebuilding the fixture with a different fleet.
        _, inside = s.call("POST", f"/vehicles/{vehicle}/blackout_windows",
                           {"start_date": d(90), "end_date": d(91)}, token=admin)
        s.check("a blacked-out car leaves availability", 200, "GET",
                f"/providers/{provider}/availability"
                f"?start_date={d(90)}&end_date={d(91)}", token=user_a)
        reduced = free_count(90, 91)
        if clear is not None and reduced == clear - 1:
            s.passed += 1
            print(f"  pass  availability drops by exactly one  [{clear} -> {reduced}]")
        else:
            s.failed.append("availability drops by exactly one")
            print(f"  FAIL  availability drops by exactly one  {clear} -> {reduced}")
        # Cancelling restores it immediately: no caching anywhere in that path.
        if isinstance(inside, dict):
            s.check("cancel the window", 204, "DELETE",
                    f"/blackout_windows/{inside['id']}", token=admin)
        restored = free_count(90, 91)
        if restored == clear:
            s.passed += 1
            print(f"  pass  cancelling restores availability  [{restored}]")
        else:
            s.failed.append("cancelling restores availability")
            print(f"  FAIL  cancelling restores availability  {clear} -> {restored}")
        # The boundary, both sides of it.
        _, adjacent = s.call("POST", f"/vehicles/{vehicle}/blackout_windows",
                             {"start_date": d(88), "end_date": d(89)}, token=admin)
        if free_count(90, 91) == clear:
            s.passed += 1
            print("  pass  a window ending the day before costs nothing  "
                  f"[{clear}]")
        else:
            s.failed.append("a window ending the day before costs nothing")
            print("  FAIL  a window ending the day before costs nothing  "
                  f"{clear} -> {free_count(90, 91)}")
        if isinstance(adjacent, dict):
            s.check("cancel the adjacent window", 204, "DELETE",
                    f"/blackout_windows/{adjacent['id']}", token=admin)

        # Ticket 41: enforcement. A class with every car in the workshop must refuse
        # a booking, and availability and booking must say the same thing. Done on
        # a class of its own so the counts are unambiguous.
        made2 = s.check("a class to black out entirely", 201, "POST",
                        f"/providers/{provider}/vehicle_classes",
                        {"name": f"Smoke Maintenance {os.getpid()}",
                         "description": "One car, taken off the road."}, token=admin)
        solo_class = made2["id"] if isinstance(made2, dict) else None
        made3 = s.check("its one car", 201, "POST",
                        f"/vehicle_classes/{solo_class}/vehicles",
                        {"plate": f"SMOKE-M{os.getpid()}"}, token=admin)
        solo_car = made3["id"] if isinstance(made3, dict) else None

        def solo_free(start: int, end: int) -> int | None:
            _, rows = s.call(
                "GET",
                f"/providers/{provider}/availability"
                f"?start_date={d(start)}&end_date={d(end)}",
                token=user_a,
            )
            for row in rows if isinstance(rows, list) else []:
                if row["vehicle_class_id"] == solo_class:
                    return row["free_count"]
            return None

        solo_booking = {
            "vehicle_class_id": solo_class,
            "pickup_branch_id": branch,
            "start_date": d(95),
            "end_date": d(96),
        }
        if solo_free(95, 96) == 1:
            s.passed += 1
            print("  pass  the new class reports one car free  [1]")
        else:
            s.failed.append("the new class reports one car free")
            print(f"  FAIL  the new class reports one car free  {solo_free(95, 96)}")
        _, grounded = s.call("POST", f"/vehicles/{solo_car}/blackout_windows",
                             {"start_date": d(95), "end_date": d(96)}, token=admin)
        if solo_free(95, 96) == 0:
            s.passed += 1
            print("  pass  availability reports zero once blacked out  [0]")
        else:
            s.failed.append("availability reports zero once blacked out")
            print(f"  FAIL  availability reports zero once blacked out  {solo_free(95, 96)}")
        # The whole point of ticket 41: the two now agree.
        s.check("booking refused for maintenance, not capacity", 409, "POST",
                f"/providers/{provider}/bookings", solo_booking, token=user_a)
        if isinstance(grounded, dict):
            s.check("cancel the window", 204, "DELETE",
                    f"/blackout_windows/{grounded['id']}", token=admin)
        s.booking_check("the same booking is then accepted", 201,
                        f"/providers/{provider}/bookings", solo_booking, user_a)
        # Re-dating onto blacked-out days is refused for owner and admin alike.
        _, again = s.call("POST", f"/vehicles/{solo_car}/blackout_windows",
                          {"start_date": d(98), "end_date": d(99)}, token=admin)
        moved = {"start_date": d(98), "end_date": d(99)}
        if s.booked:
            s.check("the owner may not re-date onto them", 409, "PUT",
                    f"/bookings/{s.booked[-1]}", moved, token=user_a)
            s.check("nor may an admin", 409, "PUT",
                    f"/bookings/{s.booked[-1]}", moved, token=admin)
        if isinstance(again, dict):
            s.check("cancel that window too", 204, "DELETE",
                    f"/blackout_windows/{again['id']}", token=admin)

        # RESTRICT: the car cannot go while it still has a service history.
        s.check("a vehicle with a window cannot be removed", 409, "DELETE",
                f"/vehicles/{vehicle}", token=admin)

        print("\n## the waitlist")
        # On a class of its own with exactly one car, so "full" is unambiguous and
        # the seeded fleet keeps the capacity it is documented as having.
        wmade = s.check("a class to fill", 201, "POST",
                        f"/providers/{provider}/vehicle_classes",
                        {"name": f"Smoke Queue {os.getpid()}",
                         "description": "One car, to be filled."}, token=admin)
        q_class = wmade["id"] if isinstance(wmade, dict) else None
        wcar = s.check("its one car", 201, "POST",
                       f"/vehicle_classes/{q_class}/vehicles",
                       {"plate": f"SMOKE-Q{os.getpid()}"}, token=admin)
        q_car = wcar["id"] if isinstance(wcar, dict) else None
        q_body = {"vehicle_class_id": q_class, "start_date": d(93), "end_date": d(94)}
        # Not full yet, so joining must be refused rather than accepted.
        s.check("joining before the class is full", 409, "POST",
                f"/providers/{provider}/waitlist_entries", q_body, token=user_a)
        # A user of its own: user_b is already at the three-active cap by now, and
        # borrowing them would fail for a reason unrelated to what is being tested.
        filler = s.register("fill")[1]
        s.booking_check("fill it", 201, f"/providers/{provider}/bookings",
                        {**q_body, "pickup_branch_id": branch}, filler)
        q1, q2 = s.register("q1")[1], s.register("q2")[1]
        e1 = s.check("first joins the queue", 201, "POST",
                     f"/providers/{provider}/waitlist_entries", q_body, token=q1)
        e2 = s.check("second joins", 201, "POST",
                     f"/providers/{provider}/waitlist_entries", q_body, token=q2)
        for label, payload, expected in (("first is position 1", e1, 1),
                                         ("second is position 2", e2, 2)):
            got = payload.get("position") if isinstance(payload, dict) else None
            if got == expected:
                s.passed += 1
                print(f"  pass  {label}  [{got}]")
            else:
                s.failed.append(label)
                print(f"  FAIL  {label}  got {got}")
        s.check("joining the same queue twice", 409, "POST",
                f"/providers/{provider}/waitlist_entries", q_body, token=q1)
        s.check("an admin joining", 403, "POST",
                f"/providers/{provider}/waitlist_entries", q_body, token=admin)
        s.check("a past-dated range", 422, "POST",
                f"/providers/{provider}/waitlist_entries",
                {**q_body, "start_date": d(-9), "end_date": d(-8)}, token=q1)
        s.check("an unexpected field", 422, "POST",
                f"/providers/{provider}/waitlist_entries",
                {**q_body, "surprise": "x"}, token=q1)
        s.check("anonymous joining", 401, "POST",
                f"/providers/{provider}/waitlist_entries", q_body)
        s.check("listing my own places", 200, "GET", "/waitlist_entries", token=q1)
        s.check("a user in no queue", 200, "GET", "/waitlist_entries", token=user_a)
        s.check("anonymous listing", 401, "GET", "/waitlist_entries")
        # `id`, not `isinstance`: a 409 body is a dict too, so testing the type
        # would walk straight into a KeyError on the error payload.
        if isinstance(e1, dict) and "id" in e1 and isinstance(e2, dict) and "id" in e2:
            s.check("another user's entry", 404, "DELETE",
                    f"/waitlist_entries/{e2['id']}", token=q1)
            s.check("an admin reaching for one", 404, "DELETE",
                    f"/waitlist_entries/{e2['id']}", token=admin)
            s.check("the first leaves", 204, "DELETE",
                    f"/waitlist_entries/{e1['id']}", token=q1)
            # q1 rejoins, so there is somebody behind the claim holder for ticket
            # 46's pass-on to reach.
            e1b = s.check("the first rejoins behind the second", 201, "POST",
                          f"/providers/{provider}/waitlist_entries", q_body,
                          token=q1)
            # Leaving must close the gap, with no renumbering to go wrong.
            _, after = s.call("GET", "/waitlist_entries", token=q2)
            moved = (isinstance(after, list) and after
                     and after[0]["position"] == 1)
            if moved:
                s.passed += 1
                print("  pass  the second moves up to position 1  [1]")
            else:
                s.failed.append("the second moves up to position 1")
                print(f"  FAIL  the second moves up to position 1  {after}")
            # Ticket 44: cancelling the booking offers the freed capacity to the
            # front of the queue, and to nobody else.
            if s.booked:
                s.check("cancel the booking that filled it", 204, "DELETE",
                        f"/bookings/{s.booked[-1]}", token=admin)
                s.booked.pop()
            _, q2_rows = s.call("GET", "/waitlist_entries", token=q2)
            offered = (isinstance(q2_rows, list) and q2_rows
                       and q2_rows[0]["offered_at"] is not None)
            if offered:
                s.passed += 1
                print("  pass  the release is offered to the front of the queue")
            else:
                s.failed.append("the release is offered to the front of the queue")
                print(f"  FAIL  the release is offered to the front  {q2_rows}")
            # An offer is an opportunity: it must not have created a booking.
            _, q2_bookings = s.call("GET", "/bookings", token=q2)
            if q2_bookings == []:
                s.passed += 1
                print("  pass  nothing was booked automatically  [[]]")
            else:
                s.failed.append("nothing was booked automatically")
                print(f"  FAIL  nothing was booked automatically  {q2_bookings}")
            # Ticket 45: the offer is a claim that holds the car against everyone
            # else, and only the holder can take it.
            if isinstance(q2_rows, list) and q2_rows:
                held = q2_rows[0]
                if held.get("state") == "claimed" and held.get("claim_expires_at"):
                    s.passed += 1
                    print("  pass  the offer is a claim with an expiry  "
                          f"[{held['state']}]")
                else:
                    s.failed.append("the offer is a claim with an expiry")
                    print(f"  FAIL  the offer is a claim with an expiry  {held}")
                # The holder was told, through the notification records.
                _, held_notes = s.call("GET", "/notifications", token=q2)
                offer_notes = [n for n in held_notes
                               if isinstance(n, dict)
                               and n.get("kind") == "waitlist_offer"]
                if offer_notes:
                    s.passed += 1
                    print("  pass  the holder was notified  [waitlist_offer]")
                else:
                    s.failed.append("the holder was notified")
                    print(f"  FAIL  the holder was notified  {held_notes}")
                # Held against everyone else, even though a car is free.
                s.check("an outsider cannot book the held car", 409, "POST",
                        f"/providers/{provider}/bookings",
                        {**q_body, "pickup_branch_id": branch}, token=user_a)
                # But the holder can.
                taken = s.check("the holder converts the claim", 201, "POST",
                                f"/waitlist_entries/{held['id']}/claim",
                                {"pickup_branch_id": branch}, token=q2)
                if isinstance(taken, dict) and "id" in taken:
                    s.booked.append(taken["id"])
                s.check("the same claim cannot be taken twice", 409, "POST",
                        f"/waitlist_entries/{held['id']}/claim",
                        {"pickup_branch_id": branch}, token=q2)
                s.check("declining a spent claim", 409, "DELETE",
                        f"/waitlist_entries/{held['id']}/claim", token=q2)
                s.check("another user reaching for the claim", 404, "POST",
                        f"/waitlist_entries/{held['id']}/claim",
                        {"pickup_branch_id": branch}, token=user_a)
                # Ticket 46: cancel the booking the claim became, which frees the car
                # again, and the person still in the queue is offered it in turn.
                if isinstance(taken, dict) and "id" in taken:
                    s.check("cancel the converted booking", 204, "DELETE",
                            f"/bookings/{taken['id']}", token=admin)
                    if taken["id"] in s.booked:
                        s.booked.remove(taken["id"])
                    _, q1_rows = s.call("GET", "/waitlist_entries", token=q1)
                    passed_on = (isinstance(q1_rows, list) and q1_rows
                                 and q1_rows[0]["state"] == "claimed")
                    if passed_on:
                        s.passed += 1
                        print("  pass  the release passes on to the next waiting  "
                              "[claimed]")
                    else:
                        s.failed.append("the release passes on to the next waiting")
                        print("  FAIL  the release passes on to the next waiting  "
                              f"{q1_rows}")
                    # Declining releases it at once and, with nobody left, the car
                    # becomes bookable by anyone again.
                    if passed_on:
                        s.check("that holder declines", 200, "DELETE",
                                f"/waitlist_entries/{q1_rows[0]['id']}/claim",
                                token=q1)
                        # A user of its own: user_a is at the three-active cap by
                        # now, and borrowing them would fail for an unrelated reason.
                        s.booking_check("the car is then bookable by anyone", 201,
                                        f"/providers/{provider}/bookings",
                                        {**q_body, "pickup_branch_id": branch},
                                        s.register("free")[1])
            s.check("the second leaves too", 204, "DELETE",
                    f"/waitlist_entries/{e2['id']}", token=q2)
        s.check("an over-large entry id", 422, "DELETE",
                "/waitlist_entries/99999999999", token=q1)

        print("\n## notifications")
        # The seeded fixture gives the demo user two, one of them unread -- nothing
        # in the service emits one yet, so without those rows there would be
        # nothing here to read.
        _, mine = s.call("GET", "/notifications", token=demo)
        s.check("list my own notifications", 200, "GET", "/notifications", token=demo)
        if isinstance(mine, list) and len(mine) >= 2:
            newest_first = all(
                mine[i]["created_at"] >= mine[i + 1]["created_at"]
                for i in range(len(mine) - 1)
            )
            if newest_first:
                s.passed += 1
                print(f"  pass  newest first  [{len(mine)} rows]")
            else:
                s.failed.append("newest first")
                print("  FAIL  newest first")
        else:
            s.skip("newest first", "the fixture has fewer than two notifications")
        # A brand-new user has none, and gets a list rather than an error.
        _, empty = s.call("GET", "/notifications", token=user_a)
        if empty == []:
            s.passed += 1
            print("  pass  a user with none gets an empty list  [[]]")
        else:
            s.failed.append("a user with none gets an empty list")
            print(f"  FAIL  a user with none gets an empty list  {empty}")
        # An admin sees their own, never everyone's -- the one collection in this
        # service that does not widen by role.
        _, as_admin = s.call("GET", "/notifications", token=admin)
        if as_admin == []:
            s.passed += 1
            print("  pass  an admin sees only their own  [[]]")
        else:
            s.failed.append("an admin sees only their own")
            print(f"  FAIL  an admin sees only their own  {as_admin}")
        if isinstance(mine, list) and mine:
            target = mine[0]["id"]
            s.check("mark one read", 200, "POST",
                    f"/notifications/{target}/read", token=demo)
            s.check("mark it read again (idempotent)", 200, "POST",
                    f"/notifications/{target}/read", token=demo)
            s.check("another user marks it read", 404, "POST",
                    f"/notifications/{target}/read", token=user_a)
            s.check("an admin marks it read", 404, "POST",
                    f"/notifications/{target}/read", token=admin)
        s.check("a notification that does not exist", 404, "POST",
                "/notifications/99999999/read", token=demo)
        s.check("an over-large notification id", 422, "POST",
                "/notifications/99999999999/read", token=demo)
        s.check("anonymous listing", 401, "GET", "/notifications")
        s.check("anonymous marking read", 401, "POST", "/notifications/1/read")
        # No route creates one. 405 means the path exists for other methods, 404
        # that it does not exist at all; either proves there is no way in.
        for method, path in (("POST", "/notifications"), ("PUT", "/notifications"),
                             ("DELETE", "/notifications/1")):
            got = s.call(method, path,
                         {"kind": "x", "message": "injected"}, token=demo)[0]
            if got in (404, 405):
                s.passed += 1
                print(f"  pass  {method} {path} is not a route  [{got}]")
            else:
                s.failed.append(f"{method} {path} is not a route")
                print(f"  FAIL  {method} {path} answered {got}")

        print("\n## quotation")
        s.check("quote a rental", 200, "POST", f"/providers/{provider}/quotations",
                booking(10, 12), token=user_a)

        print("\n## fleet routes are admin-only")
        s.check("a registered user listing classes", 200, "GET",
                f"/providers/{provider}/vehicle_classes", token=user_a)
        s.check("a registered user creating a class", 403, "POST",
                f"/providers/{provider}/vehicle_classes",
                {"name": "Nope", "description": "x"}, token=user_a)
        s.check("a registered user creating a vehicle", 403, "POST",
                f"/vehicle_classes/{klass}/vehicles", {"plate": "SMOKE-1"}, token=user_a)
        s.check("a registered user enabling a one-way route", 403, "PUT",
                f"/providers/{provider}/one_way_routes",
                {"from_branch_id": fixture["branches"][0],
                 "to_branch_id": fixture["branches"][-1]}, token=user_a)

        print("\n## tidy up")
        s.check("delete a booking of my own", 204, "DELETE", f"/bookings/{booking_a}",
                token=user_a)
        if booking_a in s.booked:
            s.booked.remove(booking_a)
        # Everything else this run created, removed as admin, so the database is
        # back to its seeded state and the run can be repeated without re-seeding.
        # Deleting a booking releases its slot immediately -- there is no cancelled
        # state -- so this is also the clean-up the domain actually supports.
        for booking_id in list(s.booked):
            s.check(f"remove booking {booking_id} created by this run", 204, "DELETE",
                    f"/bookings/{booking_id}", token=admin)
        # Windows first, then the car: the RESTRICT just demonstrated above means
        # the other order cannot work, which is itself worth leaving visible.
        for path in (f"/vehicles/{vehicle}/blackout_windows",):
            _, rows = s.call("GET", path, token=admin)
            for row in rows if isinstance(rows, list) else []:
                s.check(f"cancel window {row['id']} created by this run", 204, "DELETE",
                        f"/blackout_windows/{row['id']}", token=admin)
        s.check("remove the throwaway vehicle", 204, "DELETE", f"/vehicles/{vehicle}",
                token=admin)
        s.check("remove the maintenance-test car", 204, "DELETE",
                f"/vehicles/{solo_car}", token=admin)
        s.check("remove the maintenance-test class", 204, "DELETE",
                f"/vehicle_classes/{solo_class}", token=admin)
        # Waitlist entries hold a RESTRICT key to their class, so they go before it.
        # Converted and declined entries stay in the table by design -- they are the
        # record of what happened -- so they have to be removed explicitly, each by
        # the person who owns it, since there is no admin route into a queue.
        for queue_user in (q1, q2):
            _, left = s.call("GET", "/waitlist_entries", token=queue_user)
            for row in left if isinstance(left, list) else []:
                s.check(f"remove queue entry {row['id']}", 204, "DELETE",
                        f"/waitlist_entries/{row['id']}", token=queue_user)
        s.check("remove the queue-test car", 204, "DELETE", f"/vehicles/{q_car}",
                token=admin)
        s.check("remove the queue-test class", 204, "DELETE",
                f"/vehicle_classes/{q_class}", token=admin)

    except Precondition as error:
        print(f"\nPRECONDITION NOT MET: {error}")
        return 2
    except Exception as error:  # noqa: BLE001 -- report, never crash mid-run
        # An unexpected exception is itself a finding: usually a response shape
        # that moved under this script. Report it as a failure and still print the
        # summary, rather than dying with a traceback halfway through and leaving
        # the reader unsure how much ran.
        import traceback

        print(f"\n  FAIL  the run itself broke: {type(error).__name__}: {error}")
        traceback.print_exc()
        s.failed.append(f"the run itself broke ({type(error).__name__})")

    total = s.passed + len(s.failed)
    print(f"\n{s.passed}/{total} checks passed, {len(s.skipped)} skipped")
    if s.skipped:
        for label in s.skipped:
            print(f"  skipped: {label}")
    if s.failed:
        print("\nFAILED:")
        for label in s.failed:
            print(f"  {label}")
        return 1
    print(
        "\nAll checks passed. Every booking, review, window, vehicle and class this "
        "run created has been removed, so it can be run again without re-seeding.\n"
        "Two things it does leave behind, neither of which affects a re-run: the "
        "throwaway `smoke-*@example.com` accounts, and one seeded notification "
        "marked read (there is no route to mark one unread, by design). Re-seed to "
        "clear both."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
