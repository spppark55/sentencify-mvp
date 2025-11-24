from __future__ import annotations

import os
from typing import Dict, List

import pandas as pd
import streamlit as st
from pymongo import MongoClient
import redis

# Collection names, consistent with consumer and test scripts
LOG_A_COLLECTION = "log_a_recommend"
LOG_B_COLLECTION = "log_b_run"
LOG_C_COLLECTION = "log_c_select"
USERS_COLLECTION = "users"
FULL_DOCUMENT_STORE_COLLECTION = "full_document_store"
TRAINING_EXAMPLES_COLLECTION = "training_examples"
CONTEXT_BLOCK_STORE_COLLECTION = "context_block_store"


@st.cache_resource
def get_mongo_client(uri: str | None = None) -> MongoClient:
    """Returns a cached MongoDB client."""
    mongo_uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return MongoClient(mongo_uri)

@st.cache_resource
def get_redis_client() -> redis.Redis:
    """Returns a cached Redis client."""
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)

def get_db(mongo_uri: str | None = None, db_name: str | None = None):
    """
    Gets a specific database from a new or cached client.
    This function is also used by integration tests.
    """
    uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
    name = db_name or os.getenv("MONGO_DB_NAME", "sentencify")
    client = get_mongo_client(uri)
    return client[name]

def _collection(name: str):
    """Internal helper to get a collection from the default DB."""
    db = get_db()
    return db[name]


@st.cache_data(ttl=300)
def get_total_traffic() -> int:
    return _collection(LOG_A_COLLECTION).count_documents({})


@st.cache_data(ttl=300)
def get_micro_contexts_count() -> int:
    return _collection(CONTEXT_BLOCK_STORE_COLLECTION).count_documents({})


@st.cache_data(ttl=300)
def get_category_distribution() -> Dict[str, int]:
    pipeline = [
        {"$unwind": "$reco_options"},
        {"$group": {"_id": "$reco_options.category", "count": {"$sum": 1}}},
    ]
    rows = list(_collection(LOG_A_COLLECTION).aggregate(pipeline))
    return {row["_id"] or "unknown": row["count"] for row in rows}


@st.cache_data(ttl=300)
def get_macro_stats(bins: int = 20) -> Dict[str, List[float]]:
    cursor = _collection(FULL_DOCUMENT_STORE_COLLECTION).find({}, {"diff_ratio": 1})
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
    cursor = _collection(LOG_A_COLLECTION).find({}, {"applied_weight_doc": 1})
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
    return _collection(TRAINING_EXAMPLES_COLLECTION).count_documents({"consistency_flag": "high"})


@st.cache_data(ttl=300)
def get_acceptance_rate() -> float:
    total = _collection(LOG_C_COLLECTION).count_documents({})
    accepted = _collection(LOG_C_COLLECTION).count_documents({"was_accepted": True})
    return (accepted / total) if total else 0.0


@st.cache_data(ttl=300)
def get_user_profile_coverage(user_filter: Dict | None = None) -> float:
    """
    Calculates the ratio of users who have a generated profile embedding.
    This metric indicates how many users have enough interaction history
    to enable personalized recommendations.
    Accepts an optional filter to scope the user query.
    """
    query_filter = user_filter if user_filter is not None else {}
    
    total_users = _collection(USERS_COLLECTION).count_documents(query_filter)
    if total_users == 0:
        return 0.0
    
    # This query should match the profile structure defined in the test script.
    profile_query_filter = {**query_filter, "profile.has_embedding": True}
    users_with_profile = _collection(USERS_COLLECTION).count_documents(profile_query_filter)
    
    return users_with_profile / total_users


@st.cache_data(ttl=300)
def get_macro_etl_triggers() -> Dict[str, int]:
    total = _collection(FULL_DOCUMENT_STORE_COLLECTION).count_documents({})
    triggered = _collection(FULL_DOCUMENT_STORE_COLLECTION).count_documents({"diff_ratio": {"$gte": 0.1}})
    return {"total": total, "triggered": triggered}


@st.cache_data(ttl=300)
def get_correction_funnel_data(user_id: str | None = None) -> Dict[str, int]:
    """
    Calculates the funnel counts: View (A) -> Run (B) -> Accept (C)
    by first finding unique sessions and then looking up corresponding events.
    Optionally filters by user_id.
    """
    match_stage = {"$match": {"user_id": user_id}} if user_id else {"$match": {}}
    
    pipeline = [
        # Stage 1 (Optional): Filter by user if provided
        match_stage,
        # Stage 2: Group all Log A entries by session ID to get unique sessions
        {
            "$group": {
                "_id": "$recommend_session_id"
            }
        },
        # Stage 3: Perform lookups on these unique session IDs
        {
            "$lookup": {
                "from": LOG_B_COLLECTION,
                "localField": "_id",
                "foreignField": "recommend_session_id",
                "as": "run_b_docs"
            }
        },
        {
            "$lookup": {
                "from": LOG_C_COLLECTION,
                "let": {"session_id": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$recommend_session_id", "$$session_id"]},
                                    {"$eq": ["$was_accepted", True]}
                                ]
                            }
                        }
                    }
                ],
                "as": "accept_c_docs"
            }
        },
        # Stage 4: Group everything to get the final counts
        {
            "$group": {
                "_id": None,
                "views_a": {"$sum": 1},  # Each document now represents one unique session
                "runs_b": {"$sum": {"$cond": [{"$gt": [{"$size": "$run_b_docs"}, 0]}, 1, 0]}},
                "accepts_c": {"$sum": {"$cond": [{"$gt": [{"$size": "$accept_c_docs"}, 0]}, 1, 0]}}
            }
        },
        # Stage 5: Project to the desired output format
        {
            "$project": {
                "_id": 0,
                "views_a": 1,
                "runs_b": 1,
                "accepts_c": 1
            }
        }
    ]
    # The aggregation must start on the collection that contains the user_id filter key.
    result = list(_collection(LOG_A_COLLECTION).aggregate(pipeline))
    if not result:
        return {"views_a": 0, "runs_b": 0, "accepts_c": 0}
    return result[0]