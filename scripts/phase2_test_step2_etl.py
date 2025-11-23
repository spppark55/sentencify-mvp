#!/usr/bin/env python
"""
Standalone verification for Phase 2 Step 2 (Training ETL Pipeline).

Run: python scripts/phase2_test_step2_etl.py
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

from app.services.etl_service import run_etl_pipeline  # noqa: E402


def make_mock_mongo():
    log_c = MagicMock()
    log_c.aggregate.return_value = [
        {
            "recommend_session_id": "session-1",
            "doc_id": "doc-1",
            "field": "email",
            "was_accepted": True,
            "context_hash": "hash-1",
            "index": 0,
            "log_a": [
                {
                    "created_at": "2025-01-01T00:00:00Z",
                    "reco_options": [{"category": "email"}],
                    "P_vec": {"email": 0.8},
                    "P_doc": {"email": 0.6},
                    "applied_weight_doc": 0.3,
                    "doc_maturity_score": 0.9,
                    "is_shadow_mode": False,
                }
            ],
            "log_b": [
                {
                    "created_at": "2025-01-01T00:00:30Z",
                    "tone": "polite",
                    "llm_provider": "google",
                    "response_time_ms": 150,
                    "target_category": "email",
                }
            ],
            "log_d": [
                {
                    "field": "email",
                }
            ],
            "log_e": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                }
            ],
            "log_f": [
                {
                    "macro_category_hint": "email",
                }
            ],
        }
    ]

    training_examples = MagicMock()
    db = {
        "log_c_select": log_c,
        "training_examples": training_examples,
    }

    class DummyDB(dict):
        def __getitem__(self, item):
            if item in db:
                return db[item]
            mock_collection = MagicMock()
            db[item] = mock_collection
            return mock_collection

    dummy_db = DummyDB()

    mongo_client = MagicMock()
    mongo_client.__getitem__.return_value = dummy_db
    return mongo_client, training_examples


def run_tests() -> None:
    mongo_client, training_examples = make_mock_mongo()
    processed = run_etl_pipeline(mongo_client=mongo_client)

    assert processed == 1, "ETL should process one training example"
    assert training_examples.update_one.called, "Training examples collection not updated"
    args, kwargs = training_examples.update_one.call_args
    upsert_doc = kwargs.get("$set")
    if upsert_doc is None and len(args) >= 2:
        upsert_doc = args[1].get("$set")
    assert upsert_doc is not None, "Upsert document missing"
    assert upsert_doc["consistency_flag"] == "high", "Consistency flag should be high"

    print("✅ Phase 2 Step 2 ETL Service Test Passed")


if __name__ == "__main__":
    run_tests()
