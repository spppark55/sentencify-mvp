from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional, List
import uuid
from datetime import datetime, timezone

# 💡 [추가]: 동기 함수를 별도 스레드에서 실행하여 메인 서버 멈춤 방지
from starlette.concurrency import run_in_threadpool 

from fastapi import FastAPI, HTTPException
# Kafka 관련 패키지가 설치되어 있지 않다면 pip install kafka-python 을 추가로 해야 할 수 있습니다.
# try-except로 감싸서 Kafka가 없어도 서버가 시작되게 합니다.
try:
    from kafka import KafkaProducer 
    from kafka.errors import KafkaError # 에러 처리를 위해 임포트
except ImportError:
    KafkaProducer = None
    print("Warning: KafkaProducer not available. Kafka logging is disabled.")

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------
# 모듈 임포트
from api.app.models.kobert_classifier import get_p_rule
from api.app.models.vector_retriever import get_p_vec
from api.app.models.gemini_corrector import generate_correction
# ----------------------------------------------------------------------


class RecommendRequest(BaseModel):
    doc_id: str = Field(..., description="문서 고유 ID")
    user_id: str = Field(..., description="사용자 고유 ID")
    selected_text: str = Field(..., description="사용자가 선택(드래그)한 원문")
    context_prev: Optional[str] = Field(None, description="선택 문장 이전 문맥")
    context_next: Optional[str] = Field(None, description="선택 문장 이후 문맥")
    field: Optional[str] = Field(None, description="사용자가 직접 지정한 분야 (수동 옵션)")
    language: Optional[str] = Field(None, description="언어 (ko/en)")
    intensity: Optional[str] = Field(None, description="강도 (moderate/high)")
    user_prompt: Optional[str] = Field(None, description="사용자가 직접 입력한 프롬프트")


class RecommendOption(BaseModel):
    # --- 2. 응답 모델에 텍스트 필드 추가 ---
    text: str = Field(..., description="Gemini가 생성한 실제 교정 문장")
    category: str = Field(..., description="적용된 문장 형식 분류 (예: thesis, email)")
    language: str
    intensity: str


class RecommendResponse(BaseModel):
    insert_id: str
    recommend_session_id: str
    reco_options: List[RecommendOption]
    P_rule: Dict[str, float]
    P_vec: Dict[str, float]
    context_hash: str
    model_version: str
    api_version: str
    schema_version: str
    embedding_version: str


app = FastAPI()

# ----------------------------------------------------
# CORS 설정 (5173, 5174 포트 허용)
# ----------------------------------------------------
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "*" # 개발 편의를 위해 와일드카드 추가
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------


LOG_DIR = Path("logs")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_ENABLED = os.getenv("KAFKA_ENABLED", "true").lower() != "false"

_kafka_producer: KafkaProducer | None = None


def get_kafka_producer() -> KafkaProducer | None:
    global _kafka_producer
    if not KAFKA_ENABLED or KafkaProducer is None:
        return None
    if _kafka_producer is not None:
        return _kafka_producer
    try:
        # FastAPI 시작 시 한번만 시도하도록 수정
        _kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            api_version=(0, 10, 1), # 적절한 Kafka API 버전 지정
            # 💡 [핵심 수정 1]: 연결 타임아웃을 1초로 설정 (60초 대기 방지)
            bootstrap_servers_timeout_ms=1000,
            request_timeout_ms=1000,
            metadata_max_age_ms=1000
        )
        print("Kafka Producer initialized successfully.")
    except Exception as e:
        print(f"Warning: Could not initialize Kafka Producer. Logs will only be stored locally. Error: {e}")
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
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Error writing to local log file {filename}: {e}")


# 💡 [핵심 수정 2]: Kafka 전송을 담당하는 동기 함수 분리
def _send_kafka_sync(topic: str, payload: Dict):
    producer = get_kafka_producer()
    if producer is not None:
        try:
            # 비동기 전송 (fire-and-forget). 결과를 기다리지 않음 (.get() 제거)
            producer.send(topic, value=payload)
        except Exception as e:
            print(f"Error sending {topic} event to Kafka: {e}")

# 💡 [핵심 수정 3]: API에서 호출할 비동기 래퍼 함수들 (run_in_threadpool 사용)
async def produce_a_event(payload: Dict) -> None:
    """추천 옵션 (A) 로그를 생성 및 전송"""
    append_jsonl("a.jsonl", payload)
    await run_in_threadpool(_send_kafka_sync, "editor_recommend_options", payload)

async def produce_i_event(payload: Dict) -> None:
    """모델 스코어 (I) 로그를 생성 및 전송"""
    append_jsonl("i.jsonl", payload)
    await run_in_threadpool(_send_kafka_sync, "model_score", payload)

async def produce_e_event(payload: Dict) -> None:
    """문맥 블록 (E) 로그를 생성 및 전송"""
    append_jsonl("e.jsonl", payload)
    await run_in_threadpool(_send_kafka_sync, "context_block", payload)


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest) -> RecommendResponse:
    insert_id = str(uuid.uuid4())
    recommend_session_id = str(uuid.uuid4())

    print(f"--- [REQUEST] Received request for doc_id: {req.doc_id} ---")
    
    context_full = build_context_full(req.context_prev, req.selected_text, req.context_next)
    context_hash = build_context_hash(req.doc_id, context_full)
    
    # ----------------------------------------------------
    # --- KoBERT (P_rule) 및 Vector Search (P_vec) 호출 ---
    # ----------------------------------------------------
    
    # KoBERT 모델을 통해 문맥 형식 분류 확률 (P_rule) 획득
    try:
        # 💡 [수정]: get_p_rule이 튜플을 반환하므로 언팩킹 사용 (오류 해결)
        p_rule, rule_model_version = get_p_rule(req.selected_text, req.user_id)
    except Exception as e:
        print(f"KoBERT get_p_rule error: {e}")
        p_rule = {}
        rule_model_version = "error"

    
    # Vector DB (Qdrant) 검색을 통해 문맥 형식 확률 (P_vec) 획득
    try:
        # 💡 [수정]: get_p_vec이 튜플을 반환하므로 언팩킹 사용 (오류 해결)
        p_vec, embed_version = get_p_vec(context_full, req.user_id)
    except Exception as e:
        print(f"Vector get_p_vec error: {e}")
        p_vec = {}
        embed_version = "error"
    
    # ----------------------------------------------------
    # --- P_rule과 P_vec 융합 및 최적 형식 결정 ---
    # ----------------------------------------------------

    # P_rule과 P_vec의 가중 평균 계산 (현재는 50:50)
    final_scores: Dict[str, float] = {}
    
    # 모든 카테고리를 대상으로 융합
    all_categories = set(p_rule.keys()) | set(p_vec.keys())
    
    for k in all_categories:
        # 융합 비율은 향후 A/B 테스트나 하이퍼파라미터로 관리 가능
        score = 0.5 * p_rule.get(k, 0.0) + 0.5 * p_vec.get(k, 0.0)
        final_scores[k] = round(score, 4)

    # 최종 점수가 가장 높은 카테고리 선정
    best_category = max(final_scores, key=final_scores.get, default="general")
    language = req.language or "ko"
    intensity = req.intensity or "moderate"
    
    # 만약 사용자가 수동으로 형식을 지정했다면 그것을 우선 사용
    if req.field and req.field in all_categories:
        best_category = req.field

    # ----------------------------------------------------
    # --- Gemini (핵심) 호출: 교정 텍스트 생성 ---
    # ----------------------------------------------------
    
    # generate_correction 함수는 api/app/models/gemini_corrector.py에 구현될 예정입니다.
    try:
        # 💡 [수정]: await 키워드 추가 (비동기 함수 실행 오류 해결)
        generated_options, gemini_model_version = await generate_correction(
            original_text=req.selected_text,
            context_full=context_full,
            best_category=best_category,
            language=language,
            intensity=intensity,
            user_prompt=req.user_prompt,
            user_id=req.user_id # 개인화를 위해 user_id 전달
        )
    except Exception as e:
        print(f"Gemini generation error: {e}")
        # 오류 발생 시 빈 옵션을 반환하여 서비스 중단 방지
        generated_options = []
        gemini_model_version = "error"
        # 서비스 안정성을 위해 HTTPException 대신 내부 오류 메시지 출력 후 진행
        # raise HTTPException(status_code=500, detail=f"Correction generation failed: {e}") 

    # 생성된 텍스트 옵션을 RecommendOption Pydantic 모델로 변환
    reco_options: List[RecommendOption] = [
        RecommendOption(
            text=opt.get("text", "생성 실패"), # 생성된 텍스트
            category=opt.get("category", best_category), 
            language=language,
            intensity=intensity,
        ) 
        for opt in generated_options
    ]
    
    # 만약 옵션이 없다면 기본 옵션을 하나 추가 (프론트엔드 오류 방지)
    if not reco_options:
        reco_options.append(RecommendOption(
            text=req.selected_text, 
            category=best_category, 
            language=language, 
            intensity=intensity
        ))


    # ----------------------------------------------------
    # --- 로그 생성 (A, I, E Event) 및 응답 구성 ---
    # ----------------------------------------------------
    
    # 모델 버전 정보 업데이트
    model_version = f"KoBERT:{rule_model_version}, Vec:{embed_version}, Gemini:{gemini_model_version}"
    api_version = "v1"
    schema_version = "phase1_aie_v2" # 필드 추가로 버전 업데이트
    embedding_version = embed_version

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
        # 옵션 리스트를 딕셔너리로 변환하여 로깅
        "reco_options": [o.model_dump() for o in reco_options], 
        "P_rule": p_rule,
        "P_vec": p_vec,
        "model_version": model_version,
        "api_version": api_version,
        "schema_version": schema_version,
        "embedding_version": embedding_version,
        "created_at": _now_iso(),
    }
    # 💡 [핵심]: await을 사용하여 백그라운드 스레드로 로그 전송 (서버 안 멈춤)
    await produce_a_event(a_event)

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
    # 💡 [핵심]: await을 사용하여 백그라운드 스레드로 로그 전송
    await produce_i_event(i_event)

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
    # 💡 [핵심]: await을 사용하여 백그라운드 스레드로 로그 전송
    await produce_e_event(e_event)

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