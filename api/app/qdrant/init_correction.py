import json
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from qdrant_client.models import PointStruct, VectorParams, Distance
from .client import get_qdrant_client
from app.utils.embedding import get_embedding

# Configuration
COLLECTION_NAME = "correction_history_v1"
VECTOR_SIZE = 768
BATCH_SIZE = 100

# Path to JSON data (Relative to project root when running via scripts)
# Assuming /app/data/import inside docker, or relative path locally
DATA_FILE_PATH = Path("/app/data/import/correction_history.json")

def init_correction_collection(client):
    """correction_history_v1 컬렉션이 없으면 생성합니다."""
    if not client.collection_exists(COLLECTION_NAME):
        print(f"   [init] Creating collection: {COLLECTION_NAME}")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
    else:
        print(f"   [init] Collection {COLLECTION_NAME} already exists.")

def insert_correction_history_data():
    """JSON 파일을 읽어 Qdrant에 적재합니다."""
    client = get_qdrant_client()
    
    # 1. 컬렉션 준비
    init_correction_collection(client)

    # 2. 데이터 파일 확인
    # Local vs Docker path handling
    target_file = DATA_FILE_PATH
    if not target_file.exists():
        # Fallback for local run
        local_path = Path("data/import/correction_history.json")
        if local_path.exists():
            target_file = local_path
        else:
            print(f"⚠️  [Skip] Data file not found: {DATA_FILE_PATH} or {local_path}")
            return

    print(f"   [Read] Reading data from {target_file}...")
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading JSON: {e}")
        return

    if not data:
        print("⚠️  [Skip] JSON data is empty.")
        return

    print(f"   [Load] Found {len(data)} records. Starting upsert...")

    points = []
    total_upserted = 0

    for i, item in enumerate(data):
        try:
            # Extract Fields
            user_data = item.get("user")
            user_id = user_data.get("$oid") if isinstance(user_data, dict) else (user_data or "anonymous")
            
            original_sentence = item.get("input_sentence") or item.get("original_sentence")
            if not original_sentence:
                continue

            # Corrected Sentence Extraction
            corrected_sentence = None
            outputs = item.get("output_sentences", [])
            idx = item.get("selected_index")
            if isinstance(idx, int) and 0 <= idx < len(outputs):
                corrected_sentence = outputs[idx]
            elif outputs:
                corrected_sentence = outputs[0]

            # Payload Construction
            payload = {
                "user_id": str(user_id),
                "original_sentence": original_sentence,
                "corrected_sentence": corrected_sentence,
                "intensity": item.get("intensity", "moderate"),
                "category": item.get("field") or item.get("category", "general"),
                "timestamp": item.get("created_at", datetime.now(timezone.utc).isoformat())
            }

            # Vectorize
            vector = get_embedding(original_sentence)

            # Point Construction
            point_id = str(uuid.uuid4())
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

            # Batch Upsert
            if len(points) >= BATCH_SIZE:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                total_upserted += len(points)
                print(f"      -> Upserted batch ({total_upserted}/{len(data)})")
                points = []

        except Exception as e:
            print(f"      -> Error on item {i}: {e}")

    # Final Batch
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        total_upserted += len(points)
    
    print(f"✓ [Done] Total {total_upserted} records upserted to {COLLECTION_NAME}.")
