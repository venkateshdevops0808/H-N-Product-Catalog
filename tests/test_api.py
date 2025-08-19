# tests/test_api.py

def _paths(client):
    return {r.path for r in client.app.router.routes}

def _health_path(client):
    paths = _paths(client)
    # Prefer explicit health if you ever add it; otherwise fall back to "/"
    if "/api/v1/health" in paths:
        return "/api/v1/health"
    if "/health" in paths:
        return "/health"
    return "/"  # your app serves the index here

def _crud_paths(client):
    """Return (create_path, list_path) based on the routes the app exposes."""
    paths = _paths(client)
    if "/api/v1/items" in paths:
        return ("/api/v1/items", "/api/v1/items")
    if "/api/v1/catalog" in paths:
        return ("/api/v1/catalog", "/api/v1/catalog")
    if "/api/v1/products" in paths:
        return ("/api/v1/products", "/api/v1/products")
    raise AssertionError(f"No known CRUD routes found. Available: {sorted(paths)}")

def _extract_items(list_response_json):
    """Work with either {'items':[...], ...} or a plain list."""
    data = list_response_json
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else []

def test_health(client):
    r = client.get(_health_path(client))
    assert r.status_code == 200
    # If it's HTML for "/", that's fine; just ensure something came back.
    # If it's JSON health in the future, allow that too.
    if r.headers.get("content-type", "").startswith("application/json"):
        body = r.json()
        assert body.get("status") == "ok" or body.get("ok") is True

def test_create_and_list_catalog_item(client):
    create_path, list_path = _crud_paths(client)

    payload = {
        "name": "Protein Powder",
        "category": "supplements",
        "price": 19.99,
        "description": "whey, 1kg",
    }
    r = client.post(create_path, json=payload)
    assert r.status_code in (201, 200), r.text
    created = r.json()
    assert created.get("id", 0) > 0
    assert created.get("name") == "Protein Powder"

    r = client.get(list_path)
    assert r.status_code == 200, r.text
    items = _extract_items(r.json())
    names = [i.get("name") for i in items]
    assert "Protein Powder" in names

def test_validation_error(client):
    create_path, _ = _crud_paths(client)
    # Name empty, price negative -> should be rejected by pydantic/model rules
    r = client.post(create_path, json={"name": "", "price": -1})
    assert r.status_code in (422, 400)
