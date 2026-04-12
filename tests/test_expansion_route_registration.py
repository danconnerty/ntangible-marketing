from app.main import app


def test_expansion_web_routes_are_registered_once():
    expected_paths = [
        "/control-room/blog",
        "/control-room/science",
        "/control-room/repurposing",
    ]

    for path in expected_paths:
        matches = [
            route
            for route in app.routes
            if getattr(route, "path", None) == path and "GET" in getattr(route, "methods", set())
        ]
        assert len(matches) == 1, f"Expected one GET route for {path}, found {len(matches)}"
