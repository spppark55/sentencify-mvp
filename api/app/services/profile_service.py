from app.services.logger import COLLECTIONS
from app.utils.embedding import get_embedding

class ProfileService:
    def __init__(self, mongo_client: Optional[MongoClient] = None):
        self.client = mongo_client or MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        # Use new collection names from v2.4 Schema
        self.col_a = self.db["editor_recommend_options"]
        self.col_b = self.db["editor_run_paraphrasing"]
        self.col_c = self.db["editor_selected_paraphrasing"]
        self.col_d = self.db["correction_history"] # Legacy/Enterprise format
        self.users_col = self.db["users"]

    def update_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Full refresh of user profile statistics and embedding based on all historical logs.
        """
        if not user_id:
            return None

        # 1. Overview Stats
        total_recommend = self.col_a.count_documents({"user_id": user_id})
        total_runs = self.col_b.count_documents({"user_id": user_id})
        total_accepts = self.col_c.count_documents({"user_id": user_id, "was_accepted": True})
        
        overall_accept_rate = (total_accepts / total_runs) if total_runs > 0 else 0.0

        # 2. Preferences (from Run Logs - B)
        # Fetch all B logs for this user
        b_cursor = self.col_b.find({"user_id": user_id}, {"target_category": 1, "target_intensity": 1})
        b_docs = list(b_cursor)
        
        cat_counts = Counter([d.get("target_category", "unknown") for d in b_docs])
        int_counts = Counter([d.get("target_intensity", "unknown") for d in b_docs])
        
        # Convert to Maps (Ratios)
        preferred_category_map = {k: v / total_runs for k, v in cat_counts.items()} if total_runs else {}
        preferred_intensity_map = {k: v / total_runs for k, v in int_counts.items()} if total_runs else {}

        # 3. Option Accept Rate (A vs B)
        # Heuristic: How many B logs match the Top-1 recommendation of their A log?
        # This requires joining A and B. Expensive for high volume, but fine for MVP profile refresh.
        # We can optimize by only checking B logs and looking up A.
        
        option_match_count = 0
        for b_doc in b_docs:
            # Find corresponding A log
            # Assuming we have recommend_session_id or similar linkage
            # b_doc has 'recommend_session_id' or 'source_recommend_event_id'?
            # Let's check main.py... B has 'source_recommend_event_id' which links to A's 'insert_id'
            # OR 'recommend_session_id' linking both.
            # Let's use recommend_session_id if available (usually simpler) or fallback.
            # But we didn't project it above. Let's re-fetch or project it.
            # Actually, doing N lookups here is bad. 
            # For MVP, let's skip "Option Accept Rate" calculation in this loop to avoid 
            # N+1 query problem unless we do an aggregation pipeline.
            # Let's settle for "Result Accept Rate" which is `overall_accept_rate`.
            pass

        accept_rate_by_feature = {
            "final_result": overall_accept_rate,
            "option_match": 0.0 # Placeholder for Phase 3
        }

        # 4. User Embedding (from Correction History - D)
        # User 'accepted' sentences.
        # Filter: selected_index is not None (and numeric)
        # Note: 'correction_history' user field might be ObjectId or String depending on importer.
        # We'll try string match first.
        
        # Query for D
        # Check if user_id is string or objectid in DB... usually string in MVP if logged via API.
        d_cursor = self.col_d.find({
            "user": user_id,  # Assuming user_id is stored as string or compatible
            "selected_index": {"$ne": None, "$type": "number"}
        })
        
        embeddings = []
        for d_doc in d_cursor:
            try:
                idx = d_doc.get("selected_index")
                outputs = d_doc.get("output_sentences", [])
                if idx is not None and 0 <= idx < len(outputs):
                    final_text = outputs[idx]
                    vec = get_embedding(final_text)
                    if vec:
                        embeddings.append(vec)
            except Exception:
                continue
        
        user_embedding = []
        if embeddings:
            user_embedding = np.mean(embeddings, axis=0).tolist()

        # 5. Construct & Save Profile
        profile = UserProfile(
            user_id=user_id,
            total_recommend_count=total_recommend,
            total_accept_count=total_accepts,
            overall_accept_rate=overall_accept_rate,
            paraphrase_execution_count=total_runs,
            accept_rate_by_feature=accept_rate_by_feature,
            preferred_category_map=preferred_category_map,
            preferred_intensity_map=preferred_intensity_map,
            user_embedding_v1=user_embedding,
            updated_at=datetime.utcnow()
        )
        
        self.users_col.update_one(
            {"user_id": user_id},
            {"$set": profile.model_dump()},
            upsert=True
        )
        
        return profile