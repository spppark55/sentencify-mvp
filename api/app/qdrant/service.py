from .client import get_qdrant_client
from collections import defaultdict

# 조회
def search_vector(query_vector, limit = 15):

    client = get_qdrant_client()

    return client.query_points(
        collection_name = "context_block_v1",
        query = query_vector,
        limit = limit 
    ).points


def compute_p_vec(query_vector, limit = 15):
    results  = search_vector(query_vector, limit)
    category_scores  = defaultdict(float)

    for hit in results:
        category = hit.payload.get("field")
        if category:
            category_scores[category] += hit.score  # score 기반 가중

    total = sum(category_scores.values())

    if total > 0 :
        return {k : v/total for k,v in category_scores.items()}

    return {}


# 저장
def insert_point(point_id,vector, payload):

    client = get_qdrant_client()

    client.upsert(
        collection_name = "context_block_v1",
        points = [
            {
                "id": point_id,
                "vector" : vector,
                "payload" : payload
            }
        ]
    )