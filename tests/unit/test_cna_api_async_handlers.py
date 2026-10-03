"""No blocking work inside ``async def`` handlers (TODO.md T-705, finding PY-003).

FastAPI runs an ``async def`` endpoint on the event loop itself, so a blocking
SDK or database call inside one stalls every other request — including the
liveness probe. A plain ``def`` endpoint runs in the threadpool. The three
handlers the review named are pinned as sync here, and a structural guard keeps
the rule for every route: an ``async def`` endpoint must actually ``await``
something, otherwise it has no reason to be async.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import sys
import textwrap
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_MAIN = _REPO_ROOT / "apps" / "cna-api" / "main.py"

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None or importlib.util.find_spec("psycopg2") is None,
    reason="fastapi/psycopg2 not installed",
)


@pytest.fixture(scope="module")
def api_main() -> types.ModuleType:
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    name = "cna_api_main_under_test_async_handlers"
    spec = importlib.util.spec_from_file_location(name, _API_MAIN)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _walk_routes(routes):
    """Yield every route, descending into included routers.

    FastAPI versions differ here: some flatten ``include_router`` into the app's
    route list, newer ones append a nested router object (``original_router``)
    whose own ``routes`` hold the endpoints. Walk both shapes so the guard never
    goes blind to ``routers/*`` again.
    """
    for route in routes:
        if getattr(route, "endpoint", None) is not None:
            yield route
            continue
        nested = getattr(route, "original_router", None) or route
        child_routes = getattr(nested, "routes", None)
        if child_routes and child_routes is not routes:
            yield from _walk_routes(child_routes)


def _route_endpoints(app, api_main):
    """Routes this repository defines (main.py and routers/*), not FastAPI's own."""
    own_modules = (api_main.__name__, "routers.")
    for route in _walk_routes(app.routes):
        endpoint = route.endpoint
        if not getattr(route, "path", "").startswith("/"):
            continue
        if endpoint.__module__.startswith(own_modules):
            yield route.path, endpoint


def _awaits_something(func) -> bool:
    """True if the function body contains an await, async-with or async-for."""
    source = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(source)
    return any(
        isinstance(node, ast.Await | ast.AsyncWith | ast.AsyncFor) for node in ast.walk(tree)
    )


@pytest.mark.parametrize("name", ["test_connection", "test_connection_aws", "start_discovery"])
def test_blocking_handlers_are_plain_def(api_main, name):
    handler = getattr(api_main, name)
    assert not inspect.iscoroutinefunction(handler), (
        f"{name} performs blocking SDK/database calls and must be a plain def (T-705)"
    )


def test_every_async_route_actually_awaits(api_main):
    """An ``async def`` route with no ``await`` can only be blocking the loop."""
    offenders = []
    for path, endpoint in _route_endpoints(api_main.app, api_main):
        if inspect.iscoroutinefunction(endpoint) and not _awaits_something(endpoint):
            offenders.append(path)
    assert offenders == [], f"async routes without an await (make them plain def): {offenders}"


def test_guard_covers_the_repository_routes(api_main):
    """The walk reaches main.py and every included router — all OpenAPI paths."""
    paths = {path for path, _ in _route_endpoints(api_main.app, api_main)}
    assert {
        "/discovery/test-connection",
        "/discovery/start",
        "/health",
        "/chat/{engagement_id}",
        "/metrics/{engagement_id}",
        "/reports/{engagement_id}/encyclopedia",
        "/diagrams/{engagement_id}/generate",
    } <= paths
    assert paths == set(api_main.app.openapi()["paths"])


def test_guard_detects_an_async_router_offender(api_main):
    """A blocking async handler added through an included router is caught."""
    from fastapi import APIRouter, FastAPI

    async def offender() -> dict:  # no await: can only be blocking the loop
        return {}

    offender.__module__ = "routers.fake"
    router = APIRouter()
    router.add_api_route("/zzz-offender", offender, methods=["GET"])
    probe = FastAPI()
    probe.include_router(router)
    flagged = [
        path
        for path, endpoint in _route_endpoints(probe, api_main)
        if inspect.iscoroutinefunction(endpoint) and not _awaits_something(endpoint)
    ]
    assert flagged == ["/zzz-offender"]


def test_sync_routes_still_served(api_main):
    """The converted handlers remain routed and validate input as before."""
    from fastapi.testclient import TestClient

    with TestClient(api_main.app) as client:
        resp = client.post("/discovery/test-connection", json={})
    assert resp.status_code == 422
