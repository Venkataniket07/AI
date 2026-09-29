import os

import pytest

# Keep tests independent of any local .env / ai_config.json: no real AI calls.
os.environ["AI_ENABLED"] = "false"

from core.profile_manager import ProfileManager  # noqa: E402
from database.db_manager import DBManager  # noqa: E402


@pytest.fixture
def db(tmp_path):
    return DBManager(str(tmp_path / "test.db"), legacy_json=None)


@pytest.fixture
def profile(db):
    p = ProfileManager(db)
    p.login("tester")
    return p
