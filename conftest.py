import pytest

def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.get_closest_marker("asyncio") is None:
            if "async" in item.name or item.obj.__code__.co_flags & 0x100:
                item.add_marker(pytest.mark.asyncio)
