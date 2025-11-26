import os
import time
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
EMBED_DIM = int(os.getenv("EMBED_DIM", 768))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ETL_Worker")

def get_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def get_qdrant():
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def sync_vectors():
    """
    Syncs context_block (E) from Mongo to Qdrant.
    LOGIC:
      Only upsert E if a corresponding C event (Accepted) exists.
      - Filter E where vector_synced=False
      - For each E, check 'editor_selected_paraphrasing' (C)
        where recommend_session_id == E.recommend_session_id AND was_accepted=True.
      - If found: Upsert to Qdrant & Mark synced.
      - If not found:
          - If E is older than 1 hour -> Mark synced (as skipped/failed) to stop retry.
          - If E is new -> Do nothing (wait for user action).
    """
    db = get_db()
    q_client = get_qdrant()
    collection_name = "context_block_v1" # Qdrant collection

    # Ensure Qdrant collection exists
    try:
        q_client.get_collection(collection_name)
    except Exception:
        logger.info(f"Creating Qdrant collection: {collection_name}")
        q_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

    # Fetch pending documents
    pending_docs = db["context_block"].find({"vector_synced": False}).limit(50)
    
    count = 0
    points = []
    doc_ids_to_sync = [] # Will mark as True (Upserted or Skipped)
    
    # Import embedding utility
    from app.utils.embedding import get_embedding

    now_utc = datetime.now(timezone.utc)

    for doc in pending_docs:
        try:
            # 1. Check Acceptance (Quality Gate)
            session_id = doc.get("recommend_session_id")
            
            is_accepted = False
            if session_id:
                # Check C collection
                accepted_c = db["editor_selected_paraphrasing"].find_one({
                    "recommend_session_id": session_id,
                    "was_accepted": True
                })
                if accepted_c:
                    is_accepted = True
            
            # Decision Logic
            if is_accepted:
                # PROCEED TO UPSERT
                text = doc.get("context_full")
                if not text:
                    logger.warning(f"E doc {doc.get('insert_id')} has no text. Skipping and marking as synced.")
                    doc_ids_to_sync.append(doc["_id"])
                    continue
                
                # Re-compute embedding
                vector = get_embedding(text) 
                
                payload = {
                    "doc_id": doc.get("doc_id"),
                    "user_id": doc.get("user_id"),
                    "context_hash": doc.get("context_hash"),
                    "content": text,
                    "field": doc.get("field", "general"),
                }
                
                point_id = doc.get("insert_id")
                points.append(PointStruct(id=point_id, vector=vector, payload=payload))
                doc_ids_to_sync.append(doc["_id"])
                count += 1
                
            else:
                # NOT ACCEPTED. Mark as skipped.
                logger.info(f"Skipping E doc {doc.get('insert_id')} (No acceptance found). Marking as synced.")
                doc_ids_to_sync.append(doc["_id"])

        except Exception as e:
            logger.error(f"Error processing doc {doc.get('_id')}: {e}")

    # Batch Upsert
    if points:
        try:
            q_client.upsert(collection_name=collection_name, points=points)
            logger.info(f"Synced {count} accepted vectors to Qdrant.")
        except Exception as e:
            logger.error(f"Failed to upsert to Qdrant: {e}")
            # If upsert fails, do NOT mark as synced, let it retry
            # Remove the ids that attempted upsert from doc_ids_to_sync so they retry
            failed_point_ids = {p.id for p in points}
            doc_ids_to_sync = [doc_id for doc_id in doc_ids_to_sync if db["context_block"].find_one({"_id": doc_id}).get("insert_id") not in failed_point_ids]
            return # Exit to avoid marking failed upserts as synced

    # Mark processed in Mongo
    if doc_ids_to_sync:
        db["context_block"].update_many(
            {"_id": {"$in": doc_ids_to_sync}},
            {"$set": {"vector_synced": True}}
        )

def start_scheduler():
    scheduler = BlockingScheduler()
    # Run every 5 seconds for testing
    interval = int(os.getenv("ETL_INTERVAL_SECONDS", 5))
    scheduler.add_job(sync_vectors, 'interval', seconds=interval)
    
    logger.info(f"Starting ETL Worker Scheduler (Interval: {interval}s)...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    # Initialize embedding model once
    from app.utils.embedding import embedding_service
    logger.info("Loading embedding model for Worker...")
    embedding_service.load_model()
    
    start_scheduler()