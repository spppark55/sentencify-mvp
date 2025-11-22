import os
from typing import Dict, List, Tuple, Any

# NOTE: KoBERT 모델은 문장의 형식(Rule)을 직접 분류합니다.
# 이 파일은 통합 테스트를 위한 더미(Dummy) 로직을 포함합니다.

# KoBERT 모델 버전 명시
KOBERT_MODEL_VERSION = "kobert_cls_v2.1"


def get_p_rule(selected_text: str, user_id: str) -> Tuple[Dict[str, float], str]:
    """
    KoBERT 분류 모델을 실행하여 P_rule (문맥 형식 분류 확률 분포)를 계산합니다.
    P_rule은 선택된 텍스트 자체의 문법/어조적 특성을 기반으로 합니다.

    Args:
        selected_text (str): 사용자가 선택(드래그)한 원본 문장.
        user_id (str): 사용자 고유 ID (향후 필터링 및 개인화에 활용 가능).

    Returns:
        Tuple[Dict[str, float], str]: 
            - P_rule: 각 카테고리별 분류 확률을 담은 딕셔너리.
            - Model_Version: 사용된 KoBERT 모델 버전.
    """

    # 1. KoBERT 모델 추론 (더미 로직)
    # 실제 구현 시, KoBERT_CLASSIFIER_MODEL.predict(selected_text)를 사용합니다.

    # 2. 임시 더미 데이터 설정 
    # KoBERT는 '규칙' 기반 분류이므로, 'thesis', 'report' 등 공식적인 문서에 가중치를 두는 더미 분포
    dummy_scores = {
        "thesis": 0.45,
        "report": 0.30,
        "email": 0.15,
        "general": 0.10,
    }
    
    # 확률의 합이 1이 되도록 정규화 (더미 데이터에서는 이미 1)
    p_rule: Dict[str, float] = {k: round(v, 4) for k, v in dummy_scores.items()}

    # main.py에서 p_rule, rule_model_version = get_p_rule(...) 형태로 사용되므로 Tuple 반환
    return p_rule, KOBERT_MODEL_VERSION