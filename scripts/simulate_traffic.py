from __future__ import annotations

import json
import os
import random
import string
import time
import uuid
from datetime import datetime, timezone, timedelta

from kafka import KafkaProducer


def random_id(prefix: str = "") -> str:
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{rand}"


def now_kst_iso() -> str:
    # KST = UTC+9
    return datetime.now(timezone(timedelta(hours=9))).isoformat()


def main() -> None:
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    print(f"Connecting to Kafka at {bootstrap_servers}...")
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    user_id = "sim_user_kafka"
    doc_id = "sim_doc_kafka"

    while True:
        # 1. Session Start
        session_id = str(uuid.uuid4())
        insert_id_a = str(uuid.uuid4())
        created_at = now_kst_iso()
        latency = random.randint(50, 400)
        category = random.choice(["thesis", "article", "marketing", "report"])

        # Event A: Recommend Options
        a_event = {
            "event": "editor_recommend_options",
            "insert_id": insert_id_a,
            "recommend_session_id": session_id,
            "user_id": user_id,
            "doc_id": doc_id,
            "context_hash": random_id("ctx_"),
            "reco_category_input": category,
            "reco_options": [{"category": category}],
            "P_vec": {category: round(random.random(), 3)},
            "P_rule": {category: round(random.random(), 3)},
            "P_doc": {},
            "doc_maturity_score": 0.0,
            "applied_weight_doc": 0.0,
            "created_at": created_at,
        }
        producer.send("editor_recommend_options", value=a_event)

        # Event E: Context Block
        e_event = {
            "event": "context_block",
            "context_hash": a_event["context_hash"],
            "doc_id": doc_id,
            "user_id": user_id,
            "context_full": "Simulated context via Kafka pipeline.",
            "created_at": created_at,
        }
        producer.send("context_block", value=e_event)

        # Event I: Recommend Log
        i_event = {
            "event": "recommend_log",
            "log_id": str(uuid.uuid4()),
            "user_id": user_id,
            "doc_id": doc_id,
            "recommend_session_id": session_id,
            "P_vec": a_event["P_vec"],
            "P_rule": a_event["P_rule"],
            "latency_ms": latency,
            "created_at": created_at,
        }
        producer.send("recommend_log", value=i_event)
        print(f"[{created_at}] Sent A/E/I (Session: {session_id[:8]})")

        time.sleep(0.5)

        # Event B: Run
        b_event = {
            "event": "editor_run_paraphrasing",
            "source_recommend_event_id": insert_id_a,
            "recommend_session_id": session_id,
            "doc_id": doc_id,
            "user_id": user_id,
            "target_category": category,
            "created_at": now_kst_iso(),
        }
        producer.send("editor_run_paraphrasing", value=b_event)
        print(f"Sent B")

        time.sleep(0.5)

        # Event C: Select (Accepted)
        c_event = {
            "event": "editor_selected_paraphrasing",
            "source_recommend_event_id": insert_id_a,
            "recommend_session_id": session_id,
            "user_id": user_id,
            "doc_id": doc_id,
            "was_accepted": True,
            "created_at": now_kst_iso(),
        }
        producer.send("editor_selected_paraphrasing", value=c_event)
        print(f"Sent C (Accepted)")

        # Event K: Snapshot
        k_event = {
            "event": "editor_document_snapshot",
            "doc_id": doc_id,
            "user_id": user_id,
            "full_text": f"Simulated content at {created_at}",
            "created_at": created_at,
        }
        producer.send("editor_document_snapshot", value=k_event)
        print(f"Sent K (Snapshot)")

        pause = random.uniform(2, 5)
        print(f"--- Sleeping {pause:.1f}s ---")
        time.sleep(pause)


if __name__ == "__main__":
    main()
