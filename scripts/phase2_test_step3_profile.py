#!/usr/bin/env python
"""
Standalone verification for Phase 2 Step 3 (User Profile Service).

Run: python scripts/phase2_test_step3_profile.py
"""

from __future__ import annotations

from unittest.mock import MagicMock

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"

if "pymongo" not in sys.modules:
    pymongo_stub = MagicMock()
    pymongo_stub.MongoClient = MagicMock()
    sys.modules["pymongo"] = pymongo_stub

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.services.profile_service import CATEGORY_ORDER, update_user_profile  # noqa: E402


def make_mock_mongo():
    log_c = MagicMock()
    log_c.count_documents.side_effect = lambda query: 5 if query.get("was_accepted") else 10

    log_b = MagicMock()
    log_b.aggregate.return_value = [
        {
            "_id": None,
            "paraphrase_execution_count": 4,
            "category_counts": ["thesis", "thesis", "thesis", "email"],
            "intensity_counts": ["moderate", "moderate", "strong", "moderate"],
        }
    ]

    user_profile = MagicMock()
    db = {
        "log_c_select": log_c,
        "log_b_run": log_b,
        "user_profile": user_profile,
    }

    class DummyDB(dict):
        def __getitem__(self, item):
            return db[item]

    dummy_db = DummyDB()
    mongo_client = MagicMock()
    mongo_client.__getitem__.return_value = dummy_db
    return mongo_client, user_profile


def run_tests() -> None:
    mongo_client, user_profile_collection = make_mock_mongo()
    profile = update_user_profile("user-1", mongo_client=mongo_client)

    assert abs(profile.recommend_accept_rate - 0.5) < 1e-6, "Accept rate should be 0.5"
    thesis_index = CATEGORY_ORDER.index("thesis")
    email_index = CATEGORY_ORDER.index("email")
    assert profile.preferred_category_vector[thesis_index] > profile.preferred_category_vector[email_index]
    assert user_profile_collection.update_one.called, "user_profile collection was not updated"

    print("✅ Phase 2 Step 3 Profile Service Test Passed")


if __name__ == "__main__":
    run_tests()
