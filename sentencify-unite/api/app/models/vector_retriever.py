import os
from typing import Dict, List, Tuple, Any
from api.app.clients.qdrant_client import QdrantClient
# NOTE: 실제 환경에서는 Qdrant 클라이언트와 KLUE/BERT-base 임베딩 모델을 사용합니다.
# 이 파일은 통합 테스트를 위한 더미(Dummy) 로직을 포함합니다.

# Vector Search에 사용되는 임베딩 모델 버전 명시
EMBEDDING_MODEL_VERSION = "klue_bert_embed_v1.5"

# Qdrant 및 임베딩 설정 상수
QDRANT_COLLECTION = "sentensify_context_db"
EMBEDDING_DIM = 768


def embed_sentence(sentence: str) -> List[float]:
    """
    KLUE/BERT-base 모델을 사용하여 문장을 768차원 벡터로 임베딩합니다.
    실제 환경에서는 EMBEDDING_MODEL.encode(sentence)를 사용합니다.
    """
    # TODO: return EMBEDDING_MODEL.encode(sentence).tolist()
    # 임시 더미 벡터 반환 (실제로는 768차원 실수 벡터)
    return [0.1] * EMBEDDING_DIM


def get_p_vec(context_full: str, user_id: str) -> Tuple[Dict[str, float], str]:
    """
    Vector Search 파이프라인을 실행하여 P_vec (유사 문맥 확률 분포)를 계산합니다.
    P_vec은 TOP-K 검색 결과의 카테고리 분포를 기반으로 합니다.

    Args:
        context_full (str): 선택된 문장과 앞뒤 문맥을 포함하는 전체 텍스트.
        user_id (str): 사용자 고유 ID (향후 필터링 및 개인화에 활용 가능).

    Returns:
        Tuple[Dict[str, float], str]: 
            - P_vec: 각 카테고리별 유사도 기반 확률을 담은 딕셔너리.
            - Embedding_Version: 사용된 임베딩 모델 버전.
    """

    # 1. 입력 문맥 임베딩
    query_vector = embed_sentence(context_full)

    # 2. Qdrant 벡터 DB 검색 (TOP-K)
    # 실제 검색 로직은 다음과 같을 수 있습니다:
    # filters = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]) # 예시: 개인화 필터
    # search_results = QDRANT_CLIENT.search(
    #     collection_name=QDRANT_COLLECTION,
    #     query_vector=query_vector,
    #     limit=5, # TOP-5 검색
    #     query_filter=filters # 필터 적용
    # )

    # 3. 임시 더미 데이터 설정 (P_vec을 계산하기 위한 TOP-5 검색 결과)
    # KoBERT와 차별화된 결과 분포를 갖도록 설정 (예: thesis보다 article에 더 가중치를 둠)
    # 이는 '유사 문맥'의 특성을 반영합니다.
    dummy_top_k_categories = ["article", "article", "email", "thesis", "general"]

    # 4. 유사도 기반 범주 확률 값 도출 (P_vec 계산)
    category_counts: Dict[str, int] = {}
    for cat in dummy_top_k_categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1

    total_matches = len(dummy_top_k_categories)
    # 각 카테고리의 등장 비율을 확률로 변환
    p_vec: Dict[str, float] = {
        cat: round(count / total_matches, 4)
        for cat, count in category_counts.items()
    }
    
    # 예시 P_vec 결과: {"article": 0.4, "email": 0.2, "thesis": 0.2, "general": 0.2}

    return p_vec, EMBEDDING_MODEL_VERSION