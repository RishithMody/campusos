import os

import pytest

from tests.live.environment import live_env


def pytest_collection_modifyitems(items):
    if os.environ.get("CAMPUSOS_LIVE") != "1":
        for item in items:
            if "/live/" in str(item.path):
                item.add_marker(
                    pytest.mark.skip(reason="Set CAMPUSOS_LIVE=1 for disposable local services")
                )


@pytest.fixture
def env(request):
    yield from live_env(request)
