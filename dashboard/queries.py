from __future__ import annotations

import os
from typing import Dict, List

import pandas as pd
import streamlit as st
from pymongo import MongoClient
import redis


@st.cache_resource
def get_mongo_client() -> MongoClient:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return MongoClient(uri)


@st.cache_resource
def get_redis_client() -> redis.Redis:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)


def _collection(name: str):
    db_name = os.getenv("MONGO_DB_NAME", "sentencify")
    return get_mongo_client()[db_name][name]


@st.cache_data(ttl=300)
def get_total_traffic() -> int:
    return _collection("log_a_recommend").count_documents({})


@st.cache_data(ttl=300)
def get_micro_contexts_count() -> int:
    return _collection("context_block_store").count_documents({})


@st.cache_data(ttl=300)
def get_category_distribution() -> Dict[str, int]:
    pipeline = [
        {"$group": {"_id": "$reco_category_input", "count": {"$sum": 1}}},
    ]
    rows = list(_collection("log_a_recommend").aggregate(pipeline))
    return {row["_id"] or "unknown": row["count"] for row in rows}


@st.cache_data(ttl=300)
def get_macro_stats(bins: int = 20) -> Dict[str, List[float]]:
    cursor = _collection("full_document_store").find({}, {"diff_ratio": 1})
    diffs = [doc.get("diff_ratio", 0.0) for doc in cursor]
    if not diffs:
        return {"diffs": [], "hist": []}
    hist_series = pd.Series(diffs)
    hist = hist_series.value_counts(bins=bins, sort=False)
    return {
        "diffs": diffs,
        "hist": [{"range": str(interval), "count": int(count)} for interval, count in hist.items()],
    }


@st.cache_data(ttl=300)
def get_adaptive_weight_stats() -> Dict[str, float]:
    cursor = _collection("log_a_recommend").find({}, {"applied_weight_doc": 1})
    alphas = [doc.get("applied_weight_doc", 0.0) for doc in cursor if doc.get("applied_weight_doc") is not None]
    if not alphas:
        return {"avg_alpha": 0.0, "max_alpha": 0.0, "min_alpha": 0.0}
    series = pd.Series(alphas)
    return {
        "avg_alpha": float(series.mean()),
        "max_alpha": float(series.max()),
        "min_alpha": float(series.min()),
    }


@st.cache_data(ttl=300)
def get_cache_hit_rate() -> float:
    client = get_redis_client()
    try:
        stats = client.info("stats")
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total = hits + misses
        return (hits / total) if total else 0.0
    except Exception:
        return 0.0


@st.cache_data(ttl=300)
def get_golden_data_count() -> int:
    return _collection("training_examples").count_documents({"consistency_flag": "high"})


@st.cache_data(ttl=300)
def get_acceptance_rate() -> float:
    total = _collection("log_c_select").count_documents({})
    accepted = _collection("log_c_select").count_documents({"was_accepted": True})
    return (accepted / total) if total else 0.0


@st.cache_data(ttl=300)
def get_user_profile_coverage() -> int:
    return _collection("users").count_documents({})


@st.cache_data(ttl=300)
def get_macro_etl_triggers() -> Dict[str, int]:
    total = _collection("full_document_store").count_documents({})
    triggered = _collection("full_document_store").count_documents({"diff_ratio": {"$gte": 0.1}})
    return {"total": total, "triggered": triggered}


def get_correction_funnel() -> Dict[str, int]:
    """
    Calculates the funnel counts: View (A) -> Run (B) -> Accept (C).
    """
    return {
        "view": _collection("log_a_recommend").count_documents({}),
        "run": _collection("log_b_run").count_documents({}),
        "accept": _collection("log_c_select").count_documents({"was_accepted": True})
    }
