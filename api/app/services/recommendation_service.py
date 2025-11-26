import logging
from collections import defaultdict
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http import models
from pymongo.collection import Collection

# Constants
DEFAULT_INTENSITY = "moderate"
SEARCH_LIMIT_K = 10
QDRANT_COLLECTION_NAME = "user_behavior_v1"

logger = logging.getLogger(__name__)

from typing import List, Dict, Any, Tuple

# ... imports ...

def recommend_intensity_by_similarity(
    user_embedding: List[float],
    qdrant_client: QdrantClient,
    mongo_user_collection: Collection
) -> Tuple[str, Dict[str, Any]]:
    """
    Recommends intensity based on similar users (Weighted Voting).
    Returns: (recommended_intensity, debug_info)
    """
    debug_info = {
        "embedding_dim": 0,
        "similar_users_count": 0,
        "top_similarity_score": 0.0,
        "fallback_count": 0,
        "voting_scores": {},
        "status": "init"
    }

    if not user_embedding:
        logger.warning("Recommendation skipped: Empty user embedding.")
        debug_info["status"] = "skipped_empty_embedding"
        return DEFAULT_INTENSITY, debug_info

    debug_info["embedding_dim"] = len(user_embedding)

    try:
        # 1. Search similar users
        logger.info(f"[Rec] Searching similar users for embedding (dim={len(user_embedding)})...")
        
        search_result = qdrant_client.search(
            collection_name=QDRANT_COLLECTION_NAME,
            query_vector=user_embedding,
            limit=SEARCH_LIMIT_K,
            with_payload=["preferred_strength_vector", "preferred_intensity_map", "user_id"]
        )

        if not search_result:
            logger.info("[Rec] Cold Start: No similar users found.")
            debug_info["status"] = "cold_start_no_hits"
            return DEFAULT_INTENSITY, debug_info
            
        debug_info["similar_users_count"] = len(search_result)
        debug_info["top_similarity_score"] = float(search_result[0].score)
        logger.info(f"[Rec] Found {len(search_result)} similar users. Top score: {search_result[0].score:.4f}")

        # 2. Weighted Voting
        scores: Dict[str, float] = defaultdict(float)
        
        def normalize_key(k: str) -> str:
            return k.lower().strip()

        missing_payload_users = []

        for hit in search_result:
            payload = hit.payload or {}
            similarity = hit.score
            pref_map = payload.get("preferred_intensity_map")
            
            if not pref_map:
                user_id = payload.get("user_id")
                if user_id:
                    missing_payload_users.append(user_id)
            else:
                if isinstance(pref_map, dict):
                    for intensity, weight in pref_map.items():
                        scores[normalize_key(intensity)] += (weight * similarity)

        # Fallback
        if missing_payload_users:
            debug_info["fallback_count"] = len(missing_payload_users)
            logger.info(f"[Rec] Fallback to Mongo for {len(missing_payload_users)} users missing payload.")
            cursor = mongo_user_collection.find(
                {"user_id": {"$in": missing_payload_users}}, 
                {"user_id": 1, "preferred_intensity_map": 1}
            )
            user_prefs = {d["user_id"]: d.get("preferred_intensity_map") for d in cursor}
            
            for hit in search_result:
                uid = hit.payload.get("user_id")
                if uid in missing_payload_users and uid in user_prefs:
                    p_map = user_prefs[uid]
                    if p_map and isinstance(p_map, dict):
                        for intensity, weight in p_map.items():
                            scores[normalize_key(intensity)] += (weight * hit.score)

        # 3. Determine Winner
        if not scores:
            logger.info("[Rec] No valid intensity preferences found among similar users.")
            debug_info["status"] = "no_valid_votes"
            return DEFAULT_INTENSITY, debug_info

        best_intensity = max(scores, key=scores.get)
        
        # Update Debug Info
        debug_info["voting_scores"] = dict(scores)
        debug_info["winner"] = best_intensity
        debug_info["status"] = "success"
        
        logger.info(f"[Rec] Voting Scores: {dict(scores)}")
        logger.info(f"[Rec] Final Recommendation: {best_intensity} (Score: {scores[best_intensity]:.4f})")
        
        return best_intensity, debug_info

    except Exception as e:
        logger.error(f"Recommendation error: {e}", exc_info=True)
        debug_info["status"] = f"error: {str(e)}"
        return DEFAULT_INTENSITY, debug_info
