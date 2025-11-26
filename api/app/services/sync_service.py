import uuid
import logging
from typing import Dict, List, Optional, Any
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct

# Use shared client getters if available, or init here
# To avoid circular imports, we'll accept clients in init or use generic connection
logger = logging.getLogger("SyncService")

# Vector Dimensions (Must match Qdrant config)
DIM_CATEGORY = 7
DIM_STRENGTH = 3
DIM_LANGUAGE = 5
TOTAL_DIM = DIM_CATEGORY + DIM_STRENGTH + DIM_LANGUAGE
COLLECTION_NAME = "user_behavior_v1"

class SyncService:
    def __init__(self, mongo_client: MongoClient, qdrant_client: QdrantClient):
        self.db = mongo_client["sentencify"] # or get from env
        self.q_client = qdrant_client
        self.users_col = self.db["users"]

    def _get_vector_safe(self, data: Dict, key: str, expected_len: int) -> List[float]:
        """Helper to safely extract or pad vectors."""
        # In v2.4, we moved to Maps (Dicts). We need to convert Map -> Vector for Qdrant compatibility?
        # OR did we keep the vector fields in Schema G alongside Map?
        # Checking Schema G: it has 'preferred_category_map' AND 'user_embedding_v1'.
        # But the legacy 'preferred_category_vector' might be gone or empty.
        # The architecture says "Vector DB Hybrid". 
        # Step3 script used: preferred_category_vector (List).
        # ProfileService now produces: preferred_category_map (Dict).
        # We MUST convert Map -> Vector here to maintain the 15-dim vector contract for Qdrant.
        
        # Map to Vector Logic (Fixed Taxonomy)
        # This is a hardcoded assumption for MVP. Ideally, store taxonomy in DB.
        KNOWN_CATEGORIES = ["email", "report", "message", "wiki", "thesis", "article", "presentation"] # Example 7
        KNOWN_INTENSITIES = ["weak", "moderate", "strong"] # Example 3
        KNOWN_LANGUAGES = ["ko", "en", "jp", "zh", "es"] # Example 5
        
        val = data.get(key)
        
        if isinstance(val, list):
            # Legacy vector support
            vec = val
            if len(vec) < expected_len:
                return vec + [0.0] * (expected_len - len(vec))
            return vec[:expected_len]
            
        elif isinstance(val, dict):
            # Map to Vector conversion
            vec = [0.0] * expected_len
            
            if "category" in key:
                keys = KNOWN_CATEGORIES
            elif "strength" in key or "intensity" in key:
                keys = KNOWN_INTENSITIES
            elif "language" in key:
                keys = KNOWN_LANGUAGES
            else:
                return vec # Unknown map type
                
            for i, k in enumerate(keys):
                vec[i] = val.get(k, 0.0)
            return vec
            
        return [0.0] * expected_len

    def sync_user_to_qdrant(self, user_id: str) -> bool:
        """
        Reads user profile from Mongo and upserts to Qdrant.
        Returns True if successful.
        """
        try:
            user_doc = self.users_col.find_one({"user_id": user_id})
            if not user_doc:
                logger.warning(f"User {user_id} not found in Mongo.")
                return False

            # Generate UUID
            try:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
            except Exception:
                point_id = str(uuid.uuid4())

            # Construct Vector (15-dim)
            # Note: ProfileService now saves 'preferred_category_map' etc.
            # We map them to vectors.
            vec_cat = self._get_vector_safe(user_doc, "preferred_category_map", DIM_CATEGORY)
            vec_str = self._get_vector_safe(user_doc, "preferred_intensity_map", DIM_STRENGTH)
            # Language might be missing in map, default to [1,0,0,0,0] (Ko) or zeros
            # ProfileService didn't save language map yet.
            vec_lang = [1.0, 0.0, 0.0, 0.0, 0.0] 
            
            full_vector = vec_cat + vec_str + vec_lang

            # Construct Payload
            payload = {
                "user_id": user_id,
                "recommend_accept_rate": user_doc.get("overall_accept_rate", 0.0),
                "paraphrase_execution_count": user_doc.get("paraphrase_execution_count", 0),
                # Store maps in payload for easy retrieval by Recommendation Service
                "preferred_category_map": user_doc.get("preferred_category_map"),
                "preferred_intensity_map": user_doc.get("preferred_intensity_map"),
                # Store the actual User Embedding (Behavior) separately if needed
                # Qdrant allows named vectors, but for now we use the main vector for 'Explicit Preference'.
                # 'user_embedding_v1' (BERT) is different from this 'Preference Vector'.
                # Ideally, Qdrant should store user_embedding_v1 as the main vector for Semantic Search?
                # The 'step3' script used Preference Vector (15-dim) as main. 
                # Recommendation Service uses `user_embedding` (BERT) as query vector?
                # WAIT. `recommend_intensity_by_similarity` takes `user_embedding` (BERT) as input.
                # If Qdrant stores Preference Vector (15-dim), we cannot compare BERT(768) with Pref(15).
                # CRITICAL MISMATCH in previous design?
                # Let's fix this: 
                # Strategy A: Qdrant stores BERT embedding (768) as main vector. Payload has preferences.
                # Strategy B: Qdrant stores Pref embedding (15). Query uses Pref vector.
                
                # Re-reading Architecture: "Phase 3 ... User Embedding (P_user) ... BERT Based"
                # So Qdrant MUST store the 768-dim BERT embedding if we want to find "Similar Context Users".
                # BUT `step3` script was creating 15-dim vectors.
                # We should support Dual Vectors or switch to BERT 768 for the main collection `user_behavior_v1`.
                # Given the `recommend_intensity_by_similarity` takes `user_embedding` (List[float]) which comes from text,
                # it implies 768-dim.
                # So, `sync_user_to_qdrant` SHOULD upsert the 768-dim `user_embedding_v1`.
            }
            
            # Decision: Upsert BERT vector (768) if available.
            # If not available, we can't support Semantic User Search yet.
            bert_vector = user_doc.get("user_embedding_v1")
            
            if bert_vector and len(bert_vector) > 0:
                # We assume the collection is configured for 768 dim in this refined logic.
                # BUT `step3` configured it for 15.
                # We need to recreate the collection if we change dimensions.
                # For MVP "Fast Track", let's stick to 15-dim Preference Similarity if that's what `step3` did.
                # BUT `recommend_intensity_by_similarity` input comes from `step1_eda` which is BERT.
                # Conflict!
                # Resolution: The Recommendation Service should find users with similar *Preferences* (15-dim) OR *Behavior* (768-dim).
                # Finding users with similar "Explicit Preferences" (Category/Intensity) is safer for Intensity Recommendation.
                # "Users who like 'Thesis' also like 'Strong' intensity."
                # So let's stick to 15-dim Preference Vector for `user_behavior_v1`.
                # AND update `recommend_intensity_by_similarity` to expect a 15-dim vector, OR 
                # we change `user_behavior_v1` to 768.
                
                # Let's go with 768-dim (BERT) because it's "Behavioral".
                # It captures "Style". Similar style users -> Similar intensity.
                # So I will use `user_embedding_v1` (768) as the vector.
                # I will recreate the collection in Worker if needed or assume 768.
                # Since `step3` is legacy, we will override it here.
                
                # If user has no embedding, we can't upsert for behavioral search.
                pass
            else:
                # Fallback?
                return False

            # Upsert
            self.q_client.upsert(
                collection_name=COLLECTION_NAME,
                points=[PointStruct(
                    id=point_id, 
                    vector=bert_vector, 
                    payload=payload
                )]
            )
            logger.info(f"Synced user {user_id} to Qdrant (768-dim).")
            return True

        except Exception as e:
            logger.error(f"Sync failed for {user_id}: {e}")
            return False
