import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from kafka import KafkaConsumer
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_mongo_collection():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    return db["correction_history"]


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_qdrant_collection(client: QdrantClient) -> None:
    name = "context_block_v1"
    try:
        client.get_collection(name)
        return
    except Exception:
        # 컬렉션이 없으면 생성
        client.recreate_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=EMBED_DIM,
                distance=qmodels.Distance.COSINE,
            ),
        )


def make_stub_vector() -> list[float]:
    # 아직 임베딩 모델이 없으므로 0 벡터 Stub 사용
    return [0.0] * EMBED_DIM


def process_c_events() -> None:
    collection = get_mongo_collection()
    consumer = KafkaConsumer(
        "editor_selected_paraphrasing",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="sentencify_c_consumer",
    )
    print("[C-consumer] started, listening on topic editor_selected_paraphrasing")

    for msg in consumer:
        try:
            payload: Dict[str, Any] = msg.value
            # was_accepted 가 명시적으로 false가 아니면 저장 (기본 True)
            if payload.get("was_accepted") is False:
                continue

            doc = dict(payload)
            doc["created_at"] = now_iso()
            collection.insert_one(doc)
            print("[C-consumer] inserted correction_history document")
        except Exception as exc:
            print(f"[C-consumer] error processing message: {exc}")


def process_e_events() -> None:
    client = get_qdrant_client()
    ensure_qdrant_collection(client)

    consumer = KafkaConsumer(
        "context_block",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="sentencify_e_consumer",
    )
    print("[E-consumer] started, listening on topic context_block")

    while True:
        try:
            for msg in consumer:
                payload: Dict[str, Any] = msg.value
                point_id = str(uuid.uuid4())
                vector = make_stub_vector()

                client.upsert(
                    collection_name="context_block_v1",
                    points=[
                        qmodels.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=payload,
                        )
                    ],
                )
                print("[E-consumer] upserted point into context_block_v1")
        except Exception as exc:
            print(f"[E-consumer] error processing message: {exc}")


def main() -> None:
    threads: list[threading.Thread] = []

    t_c = threading.Thread(target=process_c_events, name="c-consumer", daemon=True)
    t_e = threading.Thread(target=process_e_events, name="e-consumer", daemon=True)

    threads.append(t_c)
    threads.append(t_e)

    for t in threads:
        t.start()

    print("[consumer] C/E consumers started. Press Ctrl+C to exit.")

    try:
        # 메인 스레드를 살아 있게 유지
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("[consumer] interrupted, shutting down...")


if __name__ == "__main__":
    main()

