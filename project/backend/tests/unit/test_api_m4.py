import pytest
from fastapi.routing import APIRoute

from app.main import app


REQUIRED_ROUTES = [
    ("POST", "/api/v1/roots"),
    ("DELETE", "/api/v1/roots/{root_id}"),
    ("POST", "/api/v1/snowflake/step5a"),
    ("POST", "/api/v1/snowflake/step5b"),
    ("POST", "/api/v1/roots/{root_id}/anchors"),
    ("GET", "/api/v1/roots/{root_id}/anchors"),
    ("PUT", "/api/v1/anchors/{id}"),
    ("POST", "/api/v1/anchors/{id}/check"),
    ("POST", "/api/v1/entities/{id}/agent/init"),
    ("GET", "/api/v1/entities/{id}/agent/state"),
    ("PUT", "/api/v1/entities/{id}/agent/desires"),
    ("POST", "/api/v1/entities/{id}/agent/decide"),
    ("POST", "/api/v1/dm/arbitrate"),
    ("POST", "/api/v1/dm/converge"),
    ("POST", "/api/v1/dm/intervene"),
    ("POST", "/api/v1/dm/replan"),
    ("POST", "/api/v1/simulation/round"),
    ("POST", "/api/v1/simulation/scene"),
    ("GET", "/api/v1/simulation/agents"),
    ("GET", "/api/v1/simulation/logs/{scene_id}"),
    ("POST", "/api/v1/render/scene"),
]


def _route_map() -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            mapping.setdefault(route.path, set()).update(route.methods or set())
    return mapping


def test_m4_api_routes_registered():
    mapping = _route_map()
    missing: list[str] = []
    for method, path in REQUIRED_ROUTES:
        methods = mapping.get(path)
        if not methods or method not in methods:
            missing.append(f"{method} {path}")
    if missing:
        pytest.fail("Missing M4 API routes: " + ", ".join(missing), pytrace=False)
