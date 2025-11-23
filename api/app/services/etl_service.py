from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from app.schemas.training import TrainingExample

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")


def _build_pipeline() -> List[Dict[str, Any]]:
    return [
        {
            "$match": {"was_accepted": True}
        },
        {
            "$lookup": {
                "from": "log_a_recommend",
                "localField": "recommend_session_id",
                "foreignField": "recommend_session_id",
                "as": "log_a",
            }
        },
        {
            "$lookup": {
                "from": "log_b_run",
                "localField": "recommend_session_id",
                "foreignField": "recommend_session_id",
                "as": "log_b",
            }
        },
        {
            "$lookup": {
                "from": "correction_history",
                "localField": "recommend_session_id",
                "foreignField": "recommend_session_id",
                "as": "log_d",
            }
        },
        {
            "$lookup": {
                "from": "context_block_store",
                "localField": "context_hash",
                "foreignField": "context_hash",
                "as": "log_e",
            }
        },
        {
            "$lookup": {
                "from": "document_context_cache",
                "localField": "doc_id",
                "foreignField": "doc_id",
                "as": "log_f",
            }
        },
    ]


def _parse_timestamp(entry: Optional[Dict[str, Any]]) -> float:
    if not entry:
        return 0.0
    created_at = entry.get("created_at")
    if created_at:
        try:
            return datetime.fromisoformat(
                str(created_at).replace("Z", "+00:00")
            ).timestamp()
        except (TypeError, ValueError):
            pass
    time_value = entry.get("time")
    if isinstance(time_value, (int, float)):
        return float(time_value) / 1000
    return 0.0


def _calc_consistency(log_a: Dict[str, Any], log_b: Dict[str, Any], log_c: Dict[str, Any]) -> str:
    if not log_a or not log_b:
        return "low"
    
    # 1. Check if source_recommend_event_id matches
    if log_b.get("source_recommend_event_id") != log_a.get("insert_id"):
        return "low"
    if log_c.get("source_recommend_event_id") != log_a.get("insert_id"):
        return "low"

    # 2. Check time difference
    ts_a = _parse_timestamp(log_a)
    ts_b = _parse_timestamp(log_b)
    if ts_a == 0 or ts_b == 0:
        return "low"
    if abs(ts_a - ts_b) > 60: # a와 b 사이 간격이 60초 초과 시 low
        return "low"
        
    return "high"


def _get_groundtruth(row: Dict[str, Any], log_d: Optional[Dict[str, Any]], log_b: Optional[Dict[str, Any]]) -> Optional[str]:
    return (
        row.get("field")
        or (log_d or {}).get("field")
        or (log_b or {}).get("target_category")
    )


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def run_etl_pipeline(mongo_client: MongoClient | None = None) -> int:
    client = mongo_client or MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    log_c = db["log_c_select"]
    training_examples = db["training_examples"]

    processed = 0
    # Add was_accepted:true filter here for efficiency
    pipeline = [{"$match": {"was_accepted": True}}] + _build_pipeline()
    
    for row in log_c.aggregate(pipeline):
        log_a = (row.get("log_a") or [None])[0]
        log_b = (row.get("log_b") or [None])[0]
        log_d = (row.get("log_d") or [None])[0]
        log_e = (row.get("log_e") or [None])[0]
        log_f = (row.get("log_f") or [None])[0]

        consistency_flag = _calc_consistency(log_a or {}, log_b or {}, row)
        
        # Rule 4.3: Use only high consistency data for training
        if consistency_flag != "high":
            continue

        example_id = row.get("recommend_session_id") or str(uuid.uuid4())

        reco_options = (log_a or {}).get("reco_options") or []
        reco_category_input = reco_options[0].get("category") if reco_options else None

        example = TrainingExample(
            example_id=example_id,
            recommend_session_id=row.get("recommend_session_id"),
            consistency_flag=consistency_flag,
            context_embedding=(log_e or {}).get("embedding") or [],
            macro_category_hint=(log_f or {}).get("macro_category_hint"),
            reco_category_input=reco_category_input,
            groundtruth_field=_get_groundtruth(row, log_d, log_b),
            was_accepted=_parse_bool(row.get("was_accepted")),
            doc_id=row.get("doc_id"),
            context_hash=row.get("context_hash"),
            source_recommend_event_id=row.get("source_recommend_event_id"),
            selected_index=row.get("index"),
            selected_sentence_id=row.get("selected_sentence_id"),
            total_paraphrasing_sentence_count=row.get("total_paraphrasing_sentence_count"),
            maintenance=row.get("maintenance"),
            target_language=row.get("target_language"),
            tone=(log_b or {}).get("tone"),
            llm_provider=(log_b or {}).get("llm_provider"),
            response_time_ms=(log_b or {}).get("response_time_ms"),
            was_shadow_mode=(log_a or {}).get("is_shadow_mode"),
            P_vec=(log_a or {}).get("P_vec") or {},
            P_doc=(log_a or {}).get("P_doc") or {},
            applied_weight_doc=(log_a or {}).get("applied_weight_doc") or 0.0,
            doc_maturity_score=(log_a or {}).get("doc_maturity_score") or 0.0,
            created_at=datetime.utcnow(),
        )

        training_examples.update_one(
            {"example_id": example.example_id},
            {"$set": example.model_dump()},
            upsert=True,
        )
        processed += 1

    return processed
