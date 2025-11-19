"""
문장 교정을 위한 프롬프트 템플릿 모듈
"""

# 카테고리별 스타일 가이드
CATEGORY_GUIDES = {
    "thesis": "학술 논문 스타일로, 객관적이고 전문적인 어투를 사용하세요. 논리적 흐름과 명확한 논증을 강조하세요.",
    "article": "기사 스타일로, 간결하고 명확한 표현을 사용하세요. 독자의 흥미를 끌면서도 정확한 정보 전달을 우선시하세요.",
    "report": "보고서 스타일로, 구조화되고 체계적인 서술을 사용하세요. 사실과 데이터를 명확히 전달하세요.",
    "marketing": "마케팅 카피 스타일로, 설득력 있고 매력적인 표현을 사용하세요. 독자의 행동을 유도하는 어조를 강조하세요.",
    "customer": "고객 상담 스타일로, 정중하고 친절한 어투를 사용하세요. 공감과 해결책 제시를 강조하세요.",
    "email": "이메일 스타일로, 비즈니스 매너를 지키면서도 간결하고 명확한 표현을 사용하세요.",
}

# 강도별 가이드
INTENSITY_GUIDES = {
    "weak": "최소한의 수정만 진행하세요. 명백한 오탈자와 문법 오류만 수정하고, 원문의 스타일과 구조를 최대한 유지하세요.",
    "moderate": "문장의 흐름과 명확성을 개선하세요. 어색한 표현을 자연스럽게 다듬고, 가독성을 높이세요.",
    "strong": "문장 구조를 적극적으로 개선하세요. 의미를 더 효과적으로 전달할 수 있도록 표현을 재구성하고, 임팩트를 강화하세요.",
}

# 프롬프트 템플릿
PARAPHRASE_TEMPLATE = """당신은 전문 교정 전문가입니다. 아래 지침에 따라 문장을 교정해 주세요.

**교정 분야**: {category}
- {category_guide}

**교정 강도**: {intensity}
- {intensity_guide}

**언어**: {language_instruction} 작성

**중요 규칙**:
1. 반드시 교정된 문장 3개만 생성하세요
2. 각 문장은 줄바꿈으로만 구분합니다
3. 번호, 불릿, 설명문, 서문 등은 일절 포함하지 마세요
4. 각 버전은 서로 다른 접근 방식이나 뉘앙스를 가져야 합니다
5. 원문의 핵심 의미는 반드시 유지하세요

---
**원본 문장**: {selected_text}
---

교정된 문장 3개:"""


def build_paraphrase_prompt(
    selected_text: str,
    category: str,
    intensity: str,
    language: str
) -> str:
    """
    카테고리별 맞춤 교정 프롬프트 생성

    Args:
        selected_text: 교정할 원본 텍스트
        category: 교정 카테고리 (논문, 기사, 보고서, 마케팅, 고객 상담, 이메일)
        intensity: 교정 강도 (weak, moderate, strong)
        language: 언어 코드 (ko, en, jp 등)

    Returns:
        완성된 프롬프트 문자열
    """
    category_guide = CATEGORY_GUIDES.get(category, "일반적인 문장 스타일로 작성하세요.")
    intensity_guide = INTENSITY_GUIDES.get(intensity, INTENSITY_GUIDES["moderate"])
    language_instruction = "한국어로" if language == "ko" else f"{language} 언어로"

    return PARAPHRASE_TEMPLATE.format(
        category=category,
        category_guide=category_guide,
        intensity=intensity,
        intensity_guide=intensity_guide,
        language_instruction=language_instruction,
        selected_text=selected_text,
    ).strip()
