"""Shared test helpers."""


def api_items(data):
    """Unwrap paginated API responses for assertions."""
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data
