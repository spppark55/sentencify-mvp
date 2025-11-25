import hashlib
import json
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaProducer
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
from openai import AsyncOpenAI
from .auth import auth_router

from app.prompts import build_paraphrase_prompt
from app.qdrant.service import compute_p_vec
from app.redis.client import get_macro_context, get_llm_cache, set_llm_cache
from app.services.macro_service import analyze_and_cache_macro_context
from app.services.classifier_service import ClassifierService
from app.utils.embedding import get_embedding, embedding_service
from app.utils.scoring import calculate_alpha, calculate_maturity_score

load_dotenv()

# ... (RecommendRequest definition omitted)

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
    P_doc: Dict[str, float]
    doc_maturity_score: float
    applied_weight_doc: float
    context_hash: str
    model_version: str
    api_version: str
    schema_version: str
    embedding_version: str


class ParaphraseRequest(BaseModel):
    doc_id: str
    user_id: str
    selected_text: str
    context_prev: Optional[str] = None
    context_next: Optional[str] = None
    category: Optional[str] = "general"
    language: Optional[str] = "ko"
    intensity: Optional[str] = "moderate"
    style_request: Optional[str] = None
    recommend_session_id: Optional[str] = None
    source_recommend_event_id: Optional[str] = None


class ParaphraseResponse(BaseModel):
    candidates: List[str]





class LogRequest(BaseModel):
    event: str

    class Config:
        extra = "allow"


class CreateDocumentRequest(BaseModel):
    user_id: str


class UpdateDocumentRequest(BaseModel):
    latest_full_text: str
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




MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

_kafka_producer: KafkaProducer | None = None
_mongo_client: MongoClient | None = None

@app.on_event("startup")
async def startup_event():
    '''임베딩 모델 및 분류기 로딩'''
    global _classifier_service
    print("Loading embedding model (klue/bert-base)")
    from app.utils.embedding import embedding_service
    embedding_service.load_model()
    print("Embedding model ready!")
    
    print("Loading KoBERT Classifier...")
    _classifier_service = ClassifierService()
    print("KoBERT Classifier ready!")

LOG_DIR = Path("logs")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() != "false"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
_openai_client: AsyncOpenAI | None = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
if OPENAI_API_KEY:
    print("[OpenAI] API key loaded from environment.")
else:
    print("[OpenAI] API key not found; paraphrase endpoint will use fallbacks.")

_kafka_producer: KafkaProducer | None = None
_mongo_client: MongoClient | None = None
_classifier_service: ClassifierService | None = None


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


def _fallback_candidates(selected_text: str) -> List[str]:
    text = selected_text or ""
    return [text, text, text]


def _clean_candidates(raw_text: str, fallback: str) -> List[str]:
    cleaned: List[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        candidate = candidate.lstrip("0123456789.-•) ").strip()
        if candidate:
            cleaned.append(candidate)
    while len(cleaned) < 3:
        cleaned.append(fallback)
    return cleaned[:3]


def _normalize_for_cache(text: str) -> str:
    """
    Normalize text to increase cache hit rate.
    - Trim whitespace
    - Remove trailing punctuation (.,!?;:)
    Example: "Hello world. " -> "Hello world"
    """
    if not text:
        return ""
    return text.strip().rstrip(".,!?;:")


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



# 문장교정 프롬프트 (레거시 호환성을 위해 유지)
# @app.post("/correct", response_model=List[str])
# async def correct(req: CorrectRequest) -> List[str]:
#     """
#     레거시 엔드포인트 - 간단한 교정용
#     프로젝트 아키텍처상으로는 /paraphrase 사용 권장
#     """
#     if not GEMINI_API_KEY:
#         raise HTTPException(
#             status_code=500,
#             detail="GEMINI_API_KEY is not configured on the server.",
#         )

#     model = genai.GenerativeModel('gemini-2.5-flash')

#     # 새로운 프롬프트 함수 사용
#     prompt = build_paraphrase_prompt(
#         selected_text=req.selected_text,
#         category=req.field or "email",
#         intensity=req.intensity or "moderate",
#         language=req.language or "ko",
#     )

#     try:
#         response = await model.generate_content_async(prompt)
#         candidates = response.text.strip().split('\n')
#         # 빈 문자열 제거
#         return [c.strip() for c in candidates if c.strip()]
#     except Exception as e:
#         print(f"Error calling Gemini API: {e}")
#         raise HTTPException(status_code=500, detail="Failed to call Gemini API.")


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
    print(
        "[TRACE][recommend] incoming request",
        {
            "doc_id": req.doc_id,
            "user_id": req.user_id,
            "selected_len": len(req.selected_text or ""),
            "context_prev_len": len(req.context_prev or ""),
            "context_next_len": len(req.context_next or ""),
            "field": req.field,
            "language": req.language,
        },
        flush=True,
    )
    try:
        macro_context = await get_macro_context(req.doc_id)
    except Exception as exc:
        print(f"[Redis] Failed to load macro context: {exc}", flush=True)
        traceback.print_exc()
        macro_context = None
    print(f"[TRACE][recommend] macro_context={macro_context}", flush=True)

    # P_rule Calculation
    p_rule: Dict[str, float] = {}
    if _classifier_service:
        p_rule = _classifier_service.predict_p_rule(context_full)
    else:
        # Fallback stub if service not loaded
        p_rule = {"thesis": 0.5, "email": 0.3, "article": 0.2}
    
    print(f"[TRACE][recommend] P_rule={p_rule}", flush=True)

    print(f"\n[DEBUG] 1. Input Context (Full):\n{context_full!r}", flush=True)

    try:
        embedding = get_embedding(context_full)
        print(
            f"[DEBUG] 2. Embedding Generated: len={len(embedding)}, "
            f"sample={embedding[:5]}...",
            flush=True,
        )
        p_vec = compute_p_vec(embedding, limit=15)
        print(f"[DEBUG] 4. Final P_vec Result: {p_vec}\n", flush=True)
        print(f"[TRACE][recommend] P_vec_keys={list(p_vec.keys())}", flush=True)
    except Exception as e:
        print(f"[ERROR] P_vec calculation failed: {e}", flush=True)
        traceback.print_exc()
        p_vec = {"thesis": 0.7, "email": 0.2, "article": 0.1}

    p_doc: Dict[str, float] = {}
    if macro_context:
        p_doc[macro_context.macro_category_hint] = 1.0
    elif p_rule:
        best_rule_category = max(p_rule, key=p_rule.get)
        p_doc[best_rule_category] = 1.0

    doc_text_for_len = (req.context_prev or "") + (req.selected_text or "") + (req.context_next or "")
    doc_length = len(doc_text_for_len)
    doc_maturity = calculate_maturity_score(doc_length)
    alpha = calculate_alpha(doc_maturity)
    print(
        f"[TRACE][recommend] doc_length={doc_length} maturity={doc_maturity:.4f} alpha={alpha:.4f}",
        flush=True,
    )

    score_categories = set(p_vec) | set(p_doc)
    if not score_categories:
        score_categories = set(p_rule)

    RULE_WEIGHT = 0.3
    vec_weight = (1 - RULE_WEIGHT) * (1 - alpha)
    doc_weight = (1 - RULE_WEIGHT) * alpha
    final_scores: Dict[str, float] = {}
    for k in score_categories:
        final_scores[k] = (
            vec_weight * p_vec.get(k, 0.0)
            + doc_weight * p_doc.get(k, 0.0)
            + RULE_WEIGHT * p_rule.get(k, 0.0)
        )

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
    print(
        "[TRACE][recommend] final reco_options",
        [opt.model_dump() for opt in reco_options],
        flush=True,
    )

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
        "P_doc": p_doc,
        "doc_maturity_score": doc_maturity,
        "applied_weight_doc": alpha,
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
        "P_doc": p_doc,
        "doc_maturity_score": doc_maturity,
        "applied_weight_doc": alpha,
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
        P_doc=p_doc,
        doc_maturity_score=doc_maturity,
        applied_weight_doc=alpha,
        context_hash=context_hash,
        model_version=model_version,
        api_version=api_version,
        schema_version=schema_version,
        embedding_version=embedding_version,
    )


@app.post("/paraphrase", response_model=ParaphraseResponse)
async def paraphrase(req: ParaphraseRequest) -> ParaphraseResponse:
    fallback_text = req.selected_text or ""
    fallback_candidates = _fallback_candidates(fallback_text)
    category = req.category or "general"
    language = req.language or "ko"
    intensity = req.intensity or "moderate"
    event_id = str(uuid.uuid4())

    # Cache Key Generation (Normalized)
    # Normalize text: "Hello." and "Hello" will share the same cache key
    normalized_text = _normalize_for_cache(req.selected_text)
    raw_key = f"{normalized_text}|{category}|{intensity}|{language}|{req.style_request or ''}"
    cache_key = f"llm:para:{hashlib.sha256(raw_key.encode()).hexdigest()}"

    # 1. Check Redis Cache
    cached_candidates = await get_llm_cache(cache_key)
    if cached_candidates:
        print(f"[Cache] Hit for key={cache_key}")
        # Log even on cache hit (optional, but good for tracking usage)
        b_event = {
            "event": "editor_run_paraphrasing",
            "event_id": event_id,
            "source_recommend_event_id": req.source_recommend_event_id,
            "recommend_session_id": req.recommend_session_id,
            "doc_id": req.doc_id,
            "user_id": req.user_id,
            "selected_text": req.selected_text,
            "context_prev": req.context_prev,
            "context_next": req.context_next,
            "target_category": category,
            "target_language": language,
            "target_intensity": intensity,
            "style_request": req.style_request,
            "created_at": _now_iso(),
            "paraphrase_llm_version": "cache-hit", # Mark as cache hit
        }
        produce_b_event(b_event)
        return ParaphraseResponse(candidates=cached_candidates)

    # 2. Cache Miss -> Call LLM
    b_event = {
        "event": "editor_run_paraphrasing",
        "event_id": event_id,
        "source_recommend_event_id": req.source_recommend_event_id,
        "recommend_session_id": req.recommend_session_id,
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "selected_text": req.selected_text,
        "context_prev": req.context_prev,
        "context_next": req.context_next,
        "target_category": category,
        "target_language": language,
        "target_intensity": intensity,
        "style_request": req.style_request,
        "created_at": _now_iso(),
        "paraphrase_llm_version": "gpt-4.1-nano",
    }
    produce_b_event(b_event)

    if _openai_client is None:
        print("OPENAI_API_KEY is not configured. Returning fallback candidates.")
        return ParaphraseResponse(candidates=fallback_candidates)

    try:
        prompt = build_paraphrase_prompt(
            selected_text=req.selected_text,
            category=category,
            intensity=intensity,
            language=language,
            style_request=req.style_request,
            context_prev=req.context_prev,
            context_next=req.context_next,
        )
        response = await _openai_client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = (
            response.choices[0].message.content if response.choices else ""
        ) or ""
        candidates = _clean_candidates(raw_text, fallback_text)
        
        # 3. Set Cache
        if candidates and candidates != fallback_candidates:
            await set_llm_cache(cache_key, candidates)
            
        return ParaphraseResponse(candidates=candidates)
    except Exception as exc:
        print(f"[OpenAI] Error during chat completion: {exc}")
        return ParaphraseResponse(candidates=fallback_candidates)


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


@app.patch("/documents/{doc_id}")
async def update_document(
    doc_id: str, req: UpdateDocumentRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    if not req.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    existing = collection.find_one({"doc_id": doc_id, "user_id": req.user_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
    prev_text = existing.get("latest_full_text") or ""
    curr_text = req.latest_full_text or ""
    len_prev = len(prev_text)
    len_curr = len(curr_text)
    denominator = max(len_prev, 1)
    diff_ratio = abs(len_curr - len_prev) / denominator
    now = _now_iso()
    collection.update_one(
        {"_id": existing["_id"]},
        {
            "$set": {
                "latest_full_text": curr_text,
                "previous_full_text": prev_text,
                "diff_ratio": diff_ratio,
                "last_synced_at": now,
            }
        },
    )
    if diff_ratio >= 0.10 and curr_text:
        print(f"[Macro] Triggering Macro ETL for doc_id={doc_id} diff_ratio={diff_ratio:.3f}")
        background_tasks.add_task(analyze_and_cache_macro_context, doc_id, curr_text)
    return {"doc_id": doc_id, "status": "updated"}
