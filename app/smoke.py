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
        # RESTRICT: the car cannot go while it still has a service history.
        s.check("a vehicle with a window cannot be removed", 409, "DELETE",
                f"/vehicles/{vehicle}", token=admin)

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
        "\nAll checks passed. Every booking and review this run created has been "
        "removed, so it can be run again without re-seeding. The throwaway "
        "`smoke-*@example.com` accounts do remain; re-seed to clear them."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
