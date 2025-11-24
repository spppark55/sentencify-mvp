from __future__ import annotations

import os
import random
import string
import time
from datetime import datetime, timezone, timedelta # Added timedelta

from pymongo import MongoClient
import redis


def mongo_client() -> MongoClient:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return MongoClient(uri)


def redis_client() -> redis.Redis:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)


def random_id(prefix: str = "") -> str:
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{rand}"


def now_kst() -> datetime:
    # KST = UTC+9
    return datetime.now(timezone(timedelta(hours=9)))


def main() -> None:
    mongo = mongo_client()[os.getenv("MONGO_DB_NAME", "sentencify")]
    redis_client()  # Reserved for future cache stats; not used directly.

    user_id = "demo_user"
    doc_id = "demo_doc"

    last_a_ts = 0.0
    last_b_ts = 0.0
    last_c_ts = 0.0
    last_k_ts = 0.0
    last_f_ts = 0.0

    last_a_id = None
    last_b_id = None
    last_session_id = None
    pending_macro_ts = None

    while True:
        # Burst: A -> B -> C (with short gaps)
        last_session_id = random_id("sess_")
        last_a_id = random_id("a_")
        created = now_kst()
        latency = random.randint(50, 400)
        category = random.choice(["thesis", "email", "article"])

        a_event = {
            "insert_id": last_a_id,
            "recommend_session_id": last_session_id,
            "user_id": user_id,
            "doc_id": doc_id,
            "context_hash": random_id("ctx_"),
            "reco_category_input": category,
            "reco_options": [{"category": category}],
            "P_vec": {category: round(random.random(), 3)},
            "P_rule": {category: round(random.random(), 3)},
            "P_doc": {},
            "P_user": {},
            "P_cluster": {},
            "weight_vec": 0.5,
            "weight_rule": 0.5,
            "weight_doc": 0.0,
            "weight_user": 0.0,
            "weight_cluster": 0.0,
            "doc_maturity_score": 0.0,
            "applied_weight_doc": 0.0,
            "latency_ms": latency,
            "created_at": created,
        }
        mongo["editor_recommend_options"].insert_one(a_event)

        e_event = {
            "context_hash": a_event["context_hash"],
            "doc_id": doc_id,
            "user_id": user_id,
            "selected_text": "sample text",
            "context_prev": "prev sentence",
            "context_next": "next sentence",
            "context_preview": "prev ... next",
            "context_full": "prev [SEP] sample text [SEP] next",
            "embedding_v1": [round(random.random(), 4) for _ in range(8)],
            "embedding_version": "v1",
            "source": "drag",
            "created_at": created,
        }
        mongo["context_block"].insert_one(e_event)

        i_log = {
            "log_id": random_id("i_"),
            "user_id": user_id,
            "doc_id": doc_id,
            "recommend_session_id": last_session_id,
            "P_vec": a_event["P_vec"],
            "P_rule": a_event["P_rule"],
            "P_doc": {},
            "P_user": {},
            "P_cluster": {},
            "weight_vec": 0.5,
            "weight_rule": 0.5,
            "weight_doc": 0.0,
            "weight_user": 0.0,
            "weight_cluster": 0.0,
            "latency_ms": latency,
            "cache_hit_macro": False,
            "cache_hit_user": False,
            "cache_hit_cluster": False,
            "model_version": "sim-v1",
            "api_version": "sim-v1",
            "schema_version": "v2.4",
            "created_at": created,
        }
        mongo["recommend_log"].insert_one(i_log)
        print(f"[{created.isoformat()}] Burst A/E/I {last_a_id}")

        time.sleep(0.5)

        last_b_id = random_id("b_")
        b_event = {
            "source_recommend_event_id": last_a_id,
            "recommend_session_id": last_session_id,
            "doc_id": doc_id,
            "user_id": user_id,
            "target_language": "ko",
            "target_intensity": "moderate",
            "target_category": "thesis",
            "created_at": now_kst(),
        }
        mongo["editor_run_paraphrasing"].insert_one(b_event)
        print(f"[{b_event['created_at'].isoformat()}] Burst B {last_b_id}")

        time.sleep(0.5)

        c_event = {
            "source_recommend_event_id": last_a_id,
            "recommend_session_id": last_session_id,
            "user_id": user_id,
            "doc_id": doc_id,
            "selected_option_index": 0,
            "was_accepted": True,
            "created_at": now_kst(),
        }
        mongo["editor_selected_paraphrasing"].insert_one(c_event)
        print(f"[{c_event['created_at'].isoformat()}] Burst C for {last_b_id}")

        # Macro trigger every burst for visual effect
        macro_now = now_kst()
        mongo["full_document_store"].update_one(
            {"doc_id": doc_id},
            {
                "$set": {
                    "latest_full_text": "demo content",
                    "previous_full_text": "demo content old",
                    "diff_ratio": 0.15,
                    "last_synced_at": macro_now,
                }
            },
            upsert=True,
        )
        pending_macro_ts = time.time()
        print(f"[{macro_now.isoformat()}] Burst Macro diff=0.15")

        # F after 2s
        time.sleep(2)
        f_doc = {
            "doc_id": doc_id,
            "macro_topic": "demo topic",
            "macro_category_hint": "demo_hint",
            "cache_hit_count": 0,
            "last_updated": now_kst(),
            "valid_until": now_kst(),
            "invalidated_by_diff": False,
            "diff_ratio": 0.15,
            "macro_llm_version": "sim-v1",
            "schema_version": "v2.4",
        }
        mongo["document_context_cache"].insert_one(f_doc)
        print(f"[{f_doc['last_updated'].isoformat()}] Burst F cache")

        pause = random.uniform(15, 20)
        print(f"--- Pausing for {pause:.1f} seconds ---")
        time.sleep(pause)


if __name__ == "__main__":
    main()
