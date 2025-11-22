from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List

from pymongo import MongoClient

from app.schemas.profile import UserProfile

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

CATEGORY_ORDER = [
    "thesis",
    "email",
    "report",
    "article",
    "marketing",
    "customer_service",
    "general",
]
INTENSITY_ORDER = ["weak", "moderate", "strong"]


def _normalize_counts(counts: Dict[str, int], order: List[str]) -> List[float]:
    total = sum(counts.get(key, 0) for key in order)
    if total <= 0:
        return [0.0 for _ in order]
    return [counts.get(key, 0) / total for key in order]


def update_user_profile(user_id: str, mongo_client: MongoClient | None = None) -> UserProfile:
    client = mongo_client or MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]

    log_c = db["log_c_select"]
    total_recs = log_c.count_documents({"user_id": user_id})
    accepted_recs = log_c.count_documents({"user_id": user_id, "was_accepted": True})
    accept_rate = (accepted_recs / total_recs) if total_recs > 0 else 0.0

    log_b = db["log_b_run"]
    pipeline = [
        {"$match": {"user_id": user_id}},
        {
            "$group": {
                "_id": None,
                "paraphrase_execution_count": {"$sum": 1},
                "category_counts": {"$push": "$field"},
                "intensity_counts": {"$push": "$maintenance"},
            }
        },
    ]
    result = list(log_b.aggregate(pipeline))
    category_counts: Dict[str, int] = {}
    intensity_counts: Dict[str, int] = {}
    paraphrase_count = 0
    if result:
        data = result[0]
        paraphrase_count = data.get("paraphrase_execution_count", 0)
        for category in data.get("category_counts", []):
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
        for intensity in data.get("intensity_counts", []):
            if intensity:
                intensity_counts[intensity] = intensity_counts.get(intensity, 0) + 1

    profile = UserProfile(
        user_id=user_id,
        preferred_category_vector=_normalize_counts(category_counts, CATEGORY_ORDER),
        preferred_strength_vector=_normalize_counts(intensity_counts, INTENSITY_ORDER),
        recommend_accept_rate=accept_rate,
        paraphrase_execution_count=paraphrase_count,
        updated_at=datetime.utcnow(),
    )

    db["user_profile"].update_one(
        {"user_id": user_id},
        {"$set": profile.model_dump()},
        upsert=True,
    )
    return profile
