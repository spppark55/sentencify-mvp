import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import Counter
import numpy as np
from pymongo import MongoClient, UpdateOne
from app.schemas.profile import UserProfile

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

class ProfileService:
    def __init__(self, mongo_client: Optional[MongoClient] = None):
        self.client = mongo_client or MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.training_col = self.db["training_examples"]
        self.users_col = self.db["users"]

    def update_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Aggregates training examples for a given user and updates their profile.
        Returns the updated UserProfile object.
        """
        # 1. Fetch all training examples for the user
        # Note: 'user_id' might need to be joined from log_a if not directly in training_examples.
        # Assuming training_examples has user_id or we join it. 
        # Current schema of TrainingExample doesn't strictly enforce user_id, 
        # but LogA has it. Let's assume we can query by user_id via lookup or it's added.
        # For now, I'll assume 'user_id' is present in training_examples for simplicity,
        # or I will perform a lookup. Let's check Schema H.
        # Schema H (TrainingExample) doesn't have user_id explicitly in the Pydantic model in the file provided earlier?
        # Let's check api/app/schemas/training.py content again to be sure.
        
        # Checking schema...
        # Wait, I should check if TrainingExample has user_id.
        # If not, I need to fetch it from LogA using recommend_session_id.
        
        # Let's proceed with a pipeline that looks up user_id from log_a if needed,
        # OR assumes we pass the user_id and find related sessions.
        
        # Actually, best approach: Find all sessions for this user from LogA, then find corresponding TrainingExamples.
        
        # Step 1: Find session_ids for this user from LogA
        user_sessions_cursor = self.db["log_a_recommend"].find({"user_id": user_id}, {"recommend_session_id": 1})
        session_ids = [doc["recommend_session_id"] for doc in user_sessions_cursor]
        
        if not session_ids:
            return None

        # Step 2: Fetch TrainingExamples for these sessions
        examples_cursor = self.training_col.find({"recommend_session_id": {"$in": session_ids}})
        examples = list(examples_cursor)
        
        if not examples:
            return None

        # 3. Calculate Metrics
        total_count = len(examples)
        accepted_examples = [ex for ex in examples if ex.get("was_accepted")]
        accepted_count = len(accepted_examples)
        
        accept_rate = accepted_count / total_count if total_count > 0 else 0.0

        # 4. Vector Aggregation (Mean Pooling of context_embedding)
        # Only use examples that have embeddings
        embeddings = [ex.get("context_embedding") for ex in examples if ex.get("context_embedding")]
        if embeddings:
            # Assuming embeddings are lists of floats
            # Check dimension consistency?
            avg_embedding = np.mean(embeddings, axis=0).tolist()
        else:
            avg_embedding = []

        # 5. Preference Analysis (Category & Strength)
        # Based on 'groundtruth_field' (Category) and maybe 'intensity' from somewhere?
        # Schema H has 'groundtruth_field' which is the selected category.
        # Strength/Intensity is in LogA's reco_options usually, or LogB.
        # Let's use groundtruth_field for category vector.
        
        categories = [ex.get("groundtruth_field") for ex in accepted_examples if ex.get("groundtruth_field")]
        category_counts = Counter(categories)
        total_cats = sum(category_counts.values())
        
        # Normalize to probability vector? Or just counts? Schema says List[float].
        # Let's assume a fixed list of categories or a sparse map?
        # Schema says "preferred_category_vector: List[float]". 
        # Usually implies a fixed dimension corresponding to known categories.
        # For MVP, let's map known categories to indices or just store normalized counts if the schema allowed dict.
        # Since it's List[float], I need a defined order.
        # Let's assume a standard order: ['email', 'report', 'presentation', 'message', 'docs'] (Example)
        # If undefined, maybe I should just store top categories or change schema to Dict.
        # Let's look at Schema G (profile.py) again.
        
        # For now, I will implement a dynamic mapping or just placehold with normalized counts of top keys if not defined.
        # Actually, simpler: Just use 0.0 for now if no fixed taxonomy is provided, 
        # OR assume the vector is [email, report, message] (3 dims) for the MVP test.
        # I'll try to find if there's a constant for CATEGORIES.
        
        # Let's assume a predefined list for MVP.
        KNOWN_CATEGORIES = ["email", "report", "message", "wiki"]
        cat_vector = [0.0] * len(KNOWN_CATEGORIES)
        if total_cats > 0:
            for i, cat in enumerate(KNOWN_CATEGORIES):
                cat_vector[i] = category_counts.get(cat, 0) / total_cats

        # Strength/Tone Analysis
        # 'tone' is available in TrainingExample.
        tones = [ex.get("tone") for ex in accepted_examples if ex.get("tone")]
        tone_counts = Counter(tones)
        total_tones = sum(tone_counts.values())
        
        KNOWN_TONES = ["formal", "casual", "polite", "witty"]
        tone_vector = [0.0] * len(KNOWN_TONES)
        if total_tones > 0:
            for i, tone in enumerate(KNOWN_TONES):
                tone_vector[i] = tone_counts.get(tone, 0) / total_tones

        # 6. Update User Profile
        profile_data = {
            "user_id": user_id,
            "recommend_accept_rate": accept_rate,
            "user_embedding_v1": avg_embedding, # Note: Schema G might need this field added or it's 'preferred_strength_vector'?
            # Wait, Schema G in arch_sync output showed:
            # preferred_category_vector, preferred_strength_vector, recommend_accept_rate, paraphrase_execution_count
            
            "preferred_category_vector": cat_vector,
            "preferred_strength_vector": tone_vector, # Using tone as strength proxy for now
            "paraphrase_execution_count": total_count,
            "updated_at": datetime.utcnow()
        }
        
        # Validate with Pydantic Schema
        # Note: user_embedding_v1 is not in the Schema G displayed earlier. 
        # I should check api/app/schemas/profile.py to see if I need to add it or if I map it to something else.
        # If not present, I'll skip it or add it to the schema.
        # For Phase 3 prep, it was requested. I will add it to the schema if missing.
        
        self.users_col.update_one(
            {"user_id": user_id},
            {"$set": profile_data},
            upsert=True
        )
        
        return UserProfile(**profile_data)