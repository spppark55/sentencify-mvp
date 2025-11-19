import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional, List
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
import google.generativeai as genai
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaProducer
from pydantic import BaseModel

from app.prompts import build_paraphrase_prompt
from app.qdrant.service import compute_p_vec
from app.utils.embedding import get_embedding, embedding_service
from pymongo import MongoClient
from .auth import auth_router

load_dotenv()


class CorrectRequest(BaseModel):
    selected_text: str
    field: Optional[str] = None
    intensity: Optional[str] = None
    language: Optional[str] = None


class ParaphraseRequest(BaseModel):
    """B 이벤트: editor_run_paraphrasing 요청"""
    source_recommend_event_id: str
    recommend_session_id: str
    doc_id: str
    user_id: str
    context_hash: str
    selected_text: str
    target_category: str
    target_language: Optional[str] = "ko"
    target_intensity: Optional[str] = "moderate"


class ParaphraseResponse(BaseModel):
    """B 이벤트 응답: 교정된 문장 후보들"""
    candidates: List[str]
    event_id: str
    recommend_session_id: str

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


class CreateDocumentRequest(BaseModel):
    user_id: str


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

# --- Gemini API Key 설정 ---
# 아래 주석을 해제하고 실제 API 키를 설정하거나,
# `GEMINI_API_KEY` 환경변수를 설정해주세요.
# os.environ['GEMINI_API_KEY'] = "YOUR_API_KEY"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

_kafka_producer: KafkaProducer | None = None
_mongo_client: MongoClient | None = None

@app.on_event("startup")
async def startup_event():
    '''임베딩 모델 로딩'''
    print("Loading embedding model (klue/bert-base)")
    from app.utils.embedding import embedding_service
    embedding_service.load_model()
    print("Embedding model ready!")


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


def get_mongo_collection(name: str):
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
    db = _mongo_client[MONGO_DB_NAME]
    return db[name]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_context_full(prev: Optional[str], selected: str, next_: Optional[str]) -> str:
    """
    Emphasize selected_text first, then lightly attach surrounding context.

    Format:
      "<selected>\\n[Context] <prev> <next>"
    """
    selected = selected or ""
    context_parts = []
    if prev:
        context_parts.append(prev)
    if next_:
        context_parts.append(next_)

    if context_parts:
        context_str = " ".join(context_parts)
        return f"{selected}\n[Context] {context_str}"

    return selected


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
    """B 이벤트: editor_run_paraphrasing 발행"""
    append_jsonl("b.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("editor_run_paraphrasing", value=payload)
        except Exception:
            pass

@app.post("/paraphrase", response_model=ParaphraseResponse)
async def paraphrase(req: ParaphraseRequest) -> ParaphraseResponse:
    """
    B 이벤트: editor_run_paraphrasing 처리
    추천(A) 이후 사용자가 실행 버튼을 눌렀을 때 호출되는 엔드포인트
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured on the server.",
        )

    event_id = str(uuid.uuid4())

    # B 이벤트 생성 및 발행
    b_event = {
        "event": "editor_run_paraphrasing",
        "event_id": event_id,
        "source_recommend_event_id": req.source_recommend_event_id,
        "recommend_session_id": req.recommend_session_id,
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "context_hash": req.context_hash,
        "target_category": req.target_category,
        "target_language": req.target_language,
        "target_intensity": req.target_intensity,
        "executed_at": _now_iso(),
        "created_at": _now_iso(),
        "paraphrase_llm_version": "gemini-2.5-flash",
    }
    produce_b_event(b_event)

    # Gemini API 호출로 교정 문장 생성
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = build_paraphrase_prompt(
            selected_text=req.selected_text,
            category=req.target_category,
            intensity=req.target_intensity,
            language=req.target_language,
        )

        response = await model.generate_content_async(prompt)
        raw_text = response.text.strip()

        # 응답 파싱: 줄바꿈으로 분리
        candidates = [c.strip() for c in raw_text.split('\n') if c.strip()]

        # 빈 결과 처리
        if not candidates:
            candidates = [req.selected_text]  # Fallback: 원문 반환

        # 최대 3개로 제한
        candidates = candidates[:3]

        return ParaphraseResponse(
            candidates=candidates,
            event_id=event_id,
            recommend_session_id=req.recommend_session_id,
        )

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # 에러 시 원문을 후보로 반환
        return ParaphraseResponse(
            candidates=[req.selected_text],
            event_id=event_id,
            recommend_session_id=req.recommend_session_id,
        )


# 문장교정 프롬프트 (레거시 호환성을 위해 유지)
@app.post("/correct", response_model=List[str])
async def correct(req: CorrectRequest) -> List[str]:
    """
    레거시 엔드포인트 - 간단한 교정용
    프로젝트 아키텍처상으로는 /paraphrase 사용 권장
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured on the server.",
        )

    model = genai.GenerativeModel('gemini-2.5-flash')

    # 새로운 프롬프트 함수 사용
    prompt = build_paraphrase_prompt(
        selected_text=req.selected_text,
        category=req.field or "email",
        intensity=req.intensity or "moderate",
        language=req.language or "ko",
    )

    try:
        response = await model.generate_content_async(prompt)
        candidates = response.text.strip().split('\n')
        # 빈 문자열 제거
        return [c.strip() for c in candidates if c.strip()]
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=500, detail="Failed to call Gemini API.")


def produce_c_event(payload: Dict) -> None:
    append_jsonl("c.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("editor_selected_paraphrasing", value=payload)
        except Exception:
            # C 이벤트도 Kafka 오류는 무시
            pass


def produce_k_event(payload: Dict) -> None:
    append_jsonl("k.jsonl", payload)
    producer = get_kafka_producer()
    if producer is not None:
        try:
            producer.send("editor_document_snapshot", value=payload)
        except Exception:
            # K 이벤트도 Kafka 오류는 무시
            pass


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest) -> RecommendResponse:
    insert_id = str(uuid.uuid4())
    recommend_session_id = str(uuid.uuid4())

    context_full = build_context_full(req.context_prev, req.selected_text, req.context_next)
    context_hash = build_context_hash(req.doc_id, context_full)

    p_rule: Dict[str, float] = {"thesis": 0.5, "email": 0.3, "article": 0.2}
    p_vec: Dict[str, float] = {"thesis": 0.7, "email": 0.2, "article": 0.1}

    
    try:
        embedding = get_embedding(context_full)
        print(
            f"[DEBUG] 2. Embedding Generated: len={len(embedding)}, "
            f"sample={embedding[:5]}...",
            flush=True,
        )
        p_vec = compute_p_vec(embedding, limit=15)
        print(f"[DEBUG] 4. Final P_vec Result: {p_vec}\n", flush=True)
    except Exception as e:
        print(f"[ERROR] P_vec calculation failed: {e}", flush=True)
        p_vec = {"thesis": 0.7, "email": 0.2, "article": 0.1}
        
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
    elif event == "editor_document_snapshot":
        produce_k_event(payload)
    else:
        append_jsonl("others.jsonl", payload)

    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth")


@app.get("/documents")
async def list_documents(user_id: str = Query(...)) -> Dict[str, Any]:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    cursor = collection.find({"user_id": user_id}).sort("last_synced_at", -1)

    items: list[Dict[str, Any]] = []
    for doc in cursor:
        doc_id = doc.get("doc_id")
        latest_full_text = doc.get("latest_full_text") or ""
        preview_text = latest_full_text[:50] if latest_full_text else "새 문서"
        last_synced_at = doc.get("last_synced_at")
        # 문자열로 정규화
        if isinstance(last_synced_at, (datetime,)):
            last_synced_at = last_synced_at.isoformat()
        items.append(
            {
                "doc_id": doc_id,
                "latest_full_text": latest_full_text,
                "preview_text": preview_text,
                "last_synced_at": last_synced_at,
            }
        )

    return {"items": items}


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    result = collection.delete_one({"doc_id": doc_id, "user_id": user_id})
    return {"deleted": result.deleted_count}


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    doc = collection.find_one({"doc_id": doc_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    latest_full_text = doc.get("latest_full_text") or ""
    last_synced_at = doc.get("last_synced_at")
    if isinstance(last_synced_at, datetime):
        last_synced_at = last_synced_at.isoformat()

    return {
        "doc_id": doc_id,
        "user_id": user_id,
        "latest_full_text": latest_full_text,
        "last_synced_at": last_synced_at,
    }


@app.post("/documents")
async def create_document(req: CreateDocumentRequest) -> Dict[str, Any]:
    if not req.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    doc_id = str(uuid.uuid4())
    now = _now_iso()

    doc = {
        "doc_id": doc_id,
        "user_id": req.user_id,
        "latest_full_text": "",
        "previous_full_text": None,
        "diff_ratio": 0.0,
        "created_at": now,
        "last_synced_at": now,
    }
    collection.insert_one(doc)

    return {"doc_id": doc_id, "created_at": now}
