import uuid
import json
from datetime import datetime, timedelta

# 1. 공통 세션 및 ID 생성 (The Chain)
session_id = str(uuid.uuid4())  # recommend_session_id
log_a_id = str(uuid.uuid4())    # insert_id (A의 PK, B/C의 FK)
doc_id = "doc_sample_001"
user_id = "user_test_01"
timestamp = datetime.utcnow()

def get_timestamp(offset_seconds=0):
    return (timestamp + timedelta(seconds=offset_seconds)).isoformat() + "Z"

# ---------------------------------------------------------
# [Step 1] Log A: 추천 발생 (Correction Required)
# ---------------------------------------------------------
log_a = {
    "insert_id": log_a_id,              # [MISSING IN CODE] 아키텍처 필수 필드
    "recommend_session_id": session_id, # [MISSING IN CODE] 아키텍처 필수 필드
    "doc_id": doc_id,
    "user_id": user_id,
    "reco_options": [
        {"category": "email", "strength": "moderate", "text": "좀 더 정중하게"},
        {"category": "report", "strength": "strong", "text": "보고서 톤으로"}
    ],
    "P_vec": {"email": 0.8, "report": 0.4},
    "P_doc": {"email": 0.9, "report": 0.2}, # Phase 1.5+
    "applied_weight_doc": 0.4,
    "doc_maturity_score": 0.7,
    "created_at": get_timestamp(0),
    "model_version": "v2.3"
}

# ---------------------------------------------------------
# [Step 2] Log B: 실행 (Run Paraphrasing)
# ---------------------------------------------------------
log_b = {
    "insert_id": str(uuid.uuid4()),
    "source_recommend_event_id": log_a_id, # A를 가리킴 (Link)
    "recommend_session_id": session_id,    # 세션 공유
    "user_id": user_id,
    "doc_id": doc_id,
    "target_language": "ko",
    "tone": "polite",
    "field": "email",
    "input_sentence_length": 15,
    "created_at": get_timestamp(2) # 2초 뒤 실행
}

# ---------------------------------------------------------
# [Step 3] Log D: Ground Truth 생성 (선택 직전/직후 생성)
# ---------------------------------------------------------
# D는 DB(_id)가 생성되면서 ID가 부여됨을 가정
log_d_id = str(uuid.uuid4()) 

log_d = {
    "_id": log_d_id,
    "user": user_id,
    "field": "email",
    "intensity": "moderate",
    "user_prompt": "좀 더 정중하게",
    "input_sentence": "이거 해줘",
    "output_sentences": ["이것을 처리해 주시겠습니까?", "이 업무를 부탁드립니다."],
    "selected_index": 0,
    "created_at": get_timestamp(4)
}

# ---------------------------------------------------------
# [Step 4] Log C: 선택 (Selection)
# ---------------------------------------------------------
log_c = {
    "insert_id": str(uuid.uuid4()),
    "source_recommend_event_id": log_a_id, # A를 가리킴
    "recommend_session_id": session_id,    # 세션 공유
    "correction_history_id": log_d_id,     # D를 가리킴 (Link)
    "user_id": user_id,
    "was_accepted": True,
    "index": 0,
    "field": "email",
    "created_at": get_timestamp(5) # 5초 뒤 선택
}

# ---------------------------------------------------------
# [Step 5] Context Block E (Micro Context)
# ---------------------------------------------------------
context_e = {
    "context_hash": "hash_xyz_123", # 실제론 hash(doc_id + text)
    "doc_id": doc_id,
    "user_id": user_id,
    "selected_text": "이거 해줘",
    "context_prev": "안녕하세요.",
    "context_next": "감사합니다.",
    "embedding_v1": [0.123] * 768, # 768-dim Mock Vector
    "created_at": get_timestamp(0)
}

# ---------------------------------------------------------
# 출력
# ---------------------------------------------------------
dataset = {
    "A": log_a,
    "B": log_b,
    "C": log_c,
    "D": log_d,
    "E": context_e
}

print(json.dumps(dataset, indent=2, ensure_ascii=False))

# 저장 파일 생성 (선택 사항)
with open("mock_golden_scenario.json", "w", encoding="utf-8") as f:
    json.dump(dataset, f, indent=2, ensure_ascii=False)