from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from pymongo import MongoClient
import redis


# Collection names aligned with v2.4 schema (A~L)
COLL_A = "editor_recommend_options"
COLL_B = "editor_run_paraphrasing"
COLL_C = "editor_selected_paraphrasing"
COLL_D = "correction_history"
COLL_E = "context_block"
COLL_F = "document_context_cache"
COLL_G = "user_profile"
COLL_H = "training_examples"
COLL_I = "recommend_log"
COLL_K = "full_document_store"
COLL_L = "editor_document_snapshot"


def _mongo_uri() -> str:
    return os.getenv("MONGO_URI", "mongodb://localhost:27017")


def _mongo_db_name() -> str:
    return os.getenv("MONGO_DB_NAME", "sentencify")


@st.cache_resource
def get_mongo_client(uri: str | None = None) -> MongoClient:
    return MongoClient(uri or _mongo_uri())


@st.cache_resource
def get_redis_client() -> redis.Redis:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)


def _db():
    return get_mongo_client()[_mongo_db_name()]


def _col(name: str):
    return _db()[name]


def _with_user(filter_obj: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    if user_id:
        filter_obj = {**filter_obj, "user_id": user_id}
    return filter_obj


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@st.cache_data(ttl=5)
def check_mongo_health() -> bool:
    try:
        _db().command("ping")
        return True
    except Exception:
        return False


@st.cache_data(ttl=5)
def check_redis_health() -> bool:
    try:
        get_redis_client().ping()
        return True
    except Exception:
        return False


@st.cache_data(ttl=5)
def check_vector_health() -> bool:
    """
    Lightweight TCP probe based on VECTOR_DB_HOST/PORT envs.
    Fallback: if TCP fails, treat as online when E docs exist in last minute (simulation).
    """
    host = os.getenv("VECTOR_DB_HOST")
    port = int(os.getenv("VECTOR_DB_PORT", "0") or "0")
    if host and port > 0:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            pass

    # Simulation fallback: recent E docs imply vector layer is "online"
    since = _now_utc() - timedelta(minutes=1)
    try:
        return _col(COLL_E).count_documents({"created_at": {"$gte": since}}) > 0
    except Exception:
        return False


def get_system_health() -> Dict[str, bool]:
    return {
        "mongo": check_mongo_health(),
        "redis": check_redis_health(),
        "vector": check_vector_health(),
    }


def _safe_count(coll: str, query: Dict[str, Any]) -> int:
    try:
        return _col(coll).count_documents(query)
    except Exception:
        return 0


@st.cache_data(ttl=5)
def get_total_counts(user_id: Optional[str] = None) -> Dict[str, int]:
    return {
        "A": _safe_count(COLL_A, _with_user({}, user_id)),
        "B": _safe_count(COLL_B, _with_user({}, user_id)),
        "C": _safe_count(COLL_C, _with_user({}, user_id)),
        "H": _safe_count(COLL_H, _with_user({}, user_id)),
        "E": _safe_count(COLL_E, _with_user({}, user_id)),
        "G": _safe_count(COLL_G, _with_user({}, user_id)),
    }


@st.cache_data(ttl=5)
def get_flow_counts(user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Returns simple stage counts for Sankey: View (A) -> Run (B) -> Accept (C) -> Golden (H).
    """
    counts = get_total_counts(user_id)
    accepts = _safe_count(COLL_C, _with_user({"was_accepted": True}, user_id))
    counts["C_accepts"] = accepts
    return counts


@st.cache_data(ttl=5)
def get_sankey_links(user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Approximates flow volumes:
    A->B: number of B events
    B->C: accepted C events
    C->H: high-consistency training examples
    """
    flows = {
        "A_to_B": _safe_count(COLL_B, _with_user({}, user_id)),
        "B_to_C": _safe_count(COLL_C, _with_user({"was_accepted": True}, user_id)),
        "C_to_H": _safe_count(COLL_H, _with_user({"consistency_flag": "high"}, user_id)),
    }
    return flows


@st.cache_data(ttl=5)
def get_asset_counts(user_id: Optional[str] = None) -> Dict[str, int]:
    return {
        "micro_contexts": _safe_count(COLL_E, _with_user({}, user_id)),
        "golden_data": _safe_count(COLL_H, _with_user({"consistency_flag": "high"}, user_id)),
    }


@st.cache_data(ttl=5)
def get_recent_a_events(limit: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = _with_user({}, user_id)
    try:
        cursor = (
            _col(COLL_A)
            .find(query, {"user_id": 1, "reco_category_input": 1, "created_at": 1, "latency_ms": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_recent_runs(limit: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = _with_user({}, user_id)
    try:
        cursor = (
            _col(COLL_B)
            .find(query, {"user_id": 1, "target_category": 1, "target_language": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_latency_series(limit: int = 50, user_id: Optional[str] = None) -> List[Tuple[datetime, float]]:
    query = _with_user({}, user_id)
    try:
        cursor = (
            _col(COLL_I)
            .find(query, {"latency_ms": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        series = [(doc.get("created_at"), float(doc.get("latency_ms", 0))) for doc in cursor if doc.get("latency_ms") is not None]
        series.reverse()
        return series
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_latency_summary(user_id: Optional[str] = None) -> Dict[str, float]:
    series = get_latency_series(limit=200, user_id=user_id)
    if not series:
        return {"avg": 0.0, "p95": 0.0}
    values = [lat for _, lat in series]
    values_sorted = sorted(values)
    p95_index = int(len(values_sorted) * 0.95) - 1
    p95_index = max(0, min(p95_index, len(values_sorted) - 1))
    return {
        "avg": sum(values) / len(values),
        "p95": values_sorted[p95_index],
    }


@st.cache_data(ttl=5)
def get_cache_hit_rate() -> float:
    try:
        stats = get_redis_client().info("stats")
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total = hits + misses
        return (hits / total) if total else 0.0
    except Exception:
        return 0.0


@st.cache_data(ttl=5)
def get_macro_queue_length() -> int:
    """Documents requiring macro refresh (diff_ratio >= 0.1)."""
    return _safe_count(COLL_K, {"diff_ratio": {"$gte": 0.1}})


@st.cache_data(ttl=5)
def get_macro_cache_samples(limit: int = 3) -> List[Dict[str, Any]]:
    try:
        cursor = (
            _col(COLL_F)
            .find({}, {"doc_id": 1, "macro_topic": 1, "macro_category_hint": 1, "last_updated": 1})
            .sort("last_updated", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_component_cost(per_call_cost: float = 0.002, user_id: Optional[str] = None) -> float:
    runs = _safe_count(COLL_B, _with_user({}, user_id))
    return round(runs * per_call_cost, 4)


def get_cost_estimate(user_id: Optional[str] = None) -> Dict[str, float]:
    cost = get_component_cost(user_id=user_id)
    queue = get_macro_queue_length()
    return {"cost": cost, "macro_queue": queue}


@st.cache_data(ttl=5)
def get_node_recency_map(user_id: Optional[str] = None, lookback_seconds: int = 60) -> Dict[str, float]:
    """
    Returns seconds since last event per component (api, worker, mongo, redis, vectordb, emb_model, genai_run, genai_macro).
    If no event in lookback window, returns 999.0.
    """
    now = _now_utc()
    since = now - timedelta(seconds=lookback_seconds)

    def age_seconds(coll: str, ts_field: str = "created_at") -> float:
        query = _with_user({ts_field: {"$gte": since}}, user_id)
        try:
            doc = _col(coll).find_one(query, sort=[(ts_field, -1)], projection={ts_field: 1})
            if not doc or not doc.get(ts_field):
                return 999.0
            delta = now - doc[ts_field]
            return max(delta.total_seconds(), 0.0)
        except Exception:
            return 999.0

    return {
        "api": age_seconds(COLL_A),
        "worker": age_seconds(COLL_K, "last_synced_at"),
        "mongo": age_seconds(COLL_A),
        "redis": age_seconds(COLL_F, "last_updated"),
        "vectordb": age_seconds(COLL_E),
        "emb_model": age_seconds(COLL_I),
        "genai_run": age_seconds(COLL_B),
        "genai_macro": age_seconds(COLL_F, "last_updated"),
    }
