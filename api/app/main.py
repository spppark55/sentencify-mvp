import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaProducer
from pydantic import BaseModel
from .auth import auth_router


class RecommendRequest(BaseModel):
    doc_id: str
    user_id: str
    selected_text: str
    context_prev: Optional[str] = None
    context_next: Optional[str] = None
    field: Optional[str] = None
    language: Optional[str] = None
    intensity: Optional[str] = None
    user_prompt: Optional[str] = None


class RecommendOption(BaseModel):
    category: str
    language: str
    intensity: str


class RecommendResponse(BaseModel):
    insert_id: str
    recommend_session_id: str
    reco_options: list[RecommendOption]
    P_rule: Dict[str, float]
    P_vec: Dict[str, float]
    context_hash: str
    model_version: str
    api_version: str
    schema_version: str
    embedding_version: str


class LogRequest(BaseModel):
    event: str

    class Config:
        extra = "allow"


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_DIR = Path("logs")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() != "false"

_kafka_producer: KafkaProducer | None = None


def get_kafka_producer() -> KafkaProducer | None:
    global _kafka_producer
    if not KAFKA_ENABLED:
        return None
    if _kafka_producer is not None:
        return _kafka_producer
    try:
        _kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        )
    except Exception:
        _kafka_producer = None
    return _kafka_producer


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_context_full(prev: Optional[str], selected: str, next_: Optional[str]) -> str:
    parts = []
    if prev:
        parts.append(prev)
    parts.append(selected)
    if next_:
        parts.append(next_)
    return "\n".join(parts)


def build_context_hash(doc_id: str, context_full: str) -> str:
    payload = f"{doc_id}:{context_full}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append_jsonl(filename: str, payload: Dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def produce_a_event(payload: Dict) -> None:
    append_jsonl("a.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("editor_recommend_options", value=payload)
        except Exception:
            # Kafka 오류가 나도 E2E 흐름은 유지
            pass


def produce_i_event(payload: Dict) -> None:
    append_jsonl("i.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("model_score", value=payload)
        except Exception:
            pass


def produce_e_event(payload: Dict) -> None:
    append_jsonl("e.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("context_block", value=payload)
        except Exception:
            pass


def produce_b_event(payload: Dict) -> None:
    append_jsonl("b.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("editor_run_paraphrasing", value=payload)
        except Exception:
            # B 이벤트는 로그용이므로 Kafka 오류는 무시
            pass


def produce_c_event(payload: Dict) -> None:
    append_jsonl("c.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("editor_selected_paraphrasing", value=payload)
        except Exception:
            # C 이벤트도 Kafka 오류는 무시
            pass


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest) -> RecommendResponse:
    insert_id = str(uuid.uuid4())
    recommend_session_id = str(uuid.uuid4())

    context_full = build_context_full(req.context_prev, req.selected_text, req.context_next)
    context_hash = build_context_hash(req.doc_id, context_full)

    p_rule: Dict[str, float] = {"thesis": 0.5, "email": 0.3, "article": 0.2}
    p_vec: Dict[str, float] = {"thesis": 0.7, "email": 0.2, "article": 0.1}

    final_scores: Dict[str, float] = {}
    for k in set(p_rule) | set(p_vec):
        final_scores[k] = 0.5 * p_rule.get(k, 0.0) + 0.5 * p_vec.get(k, 0.0)

    best_category = max(final_scores, key=final_scores.get)
    language = req.language or "ko"
    intensity = req.intensity or "moderate"

    reco_options = [
        RecommendOption(
            category=best_category,
            language=language,
            intensity=intensity,
        )
    ]

    model_version = "phase1_stub_v1"
    api_version = "v1"
    schema_version = "phase1_aie_v1"
    embedding_version = "embed_v1_stub"

    a_event = {
        "event": "editor_recommend_options",
        "insert_id": insert_id,
        "recommend_session_id": recommend_session_id,
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "selected_text": req.selected_text,
        "context_prev": req.context_prev,
        "context_next": req.context_next,
        "context_hash": context_hash,
        "context_full_preview": context_full[:500],
        "reco_options": [o.model_dump() for o in reco_options],
        "P_rule": p_rule,
        "P_vec": p_vec,
        "model_version": model_version,
        "api_version": api_version,
        "schema_version": schema_version,
        "embedding_version": embedding_version,
        "created_at": _now_iso(),
    }
    produce_a_event(a_event)

    i_event = {
        "event": "model_score",
        "insert_id": str(uuid.uuid4()),
        "source_recommend_event_id": insert_id,
        "recommend_session_id": recommend_session_id,
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "context_hash": context_hash,
        "P_rule": p_rule,
        "P_vec": p_vec,
        "model_version": model_version,
        "api_version": api_version,
        "schema_version": schema_version,
        "created_at": _now_iso(),
    }
    produce_i_event(i_event)

    e_event = {
        "event": "context_block",
        "insert_id": str(uuid.uuid4()),
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "context_hash": context_hash,
        "context_full": context_full,
        "embedding_version": embedding_version,
        "created_at": _now_iso(),
    }
    produce_e_event(e_event)

    return RecommendResponse(
        insert_id=insert_id,
        recommend_session_id=recommend_session_id,
        reco_options=reco_options,
        P_rule=p_rule,
        P_vec=p_vec,
        context_hash=context_hash,
        model_version=model_version,
        api_version=api_version,
        schema_version=schema_version,
        embedding_version=embedding_version,
    )


@app.post("/log")
async def log_event(req: LogRequest) -> Dict[str, Any]:
    payload: Dict[str, Any] = req.model_dump()
    event = payload.get("event")

    if event == "editor_run_paraphrasing":
        produce_b_event(payload)
    elif event == "editor_selected_paraphrasing":
        produce_c_event(payload)
    else:
        append_jsonl("others.jsonl", payload)

    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth")
