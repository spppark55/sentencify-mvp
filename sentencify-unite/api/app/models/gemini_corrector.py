import json
import os
import httpx
from typing import Dict, List, Any, Tuple, Optional
from tenacity import retry, wait_exponential, stop_after_attempt
import asyncio

# 환경 변수에서 API 키를 가져오거나 더미로 설정
API_KEY = os.getenv("GEMINI_API_KEY", "")

# 💡 [수정]: 가장 안정적이고 빠른 최신 모델 사용
MODEL_NAME = "gemini-1.5-flash"
GEMINI_MODEL_VERSION = MODEL_NAME

# API URL
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"


@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3))
async def call_gemini_api(payload: Dict) -> Dict:
    """
    Gemini API를 호출하며, 지수 백오프(Exponential Backoff)를 적용합니다.
    """
    headers = {'Content-Type': 'application/json'}
    
    # 1. API 키 누락 시 Mock 처리 (서버 다운 방지)
    if not API_KEY:
        print("[Gemini] API Key not found. Using Mock response.")
        await asyncio.sleep(0.01) 
        mock_json_response = json.dumps({
            "options": [
                "[Mock] API 키가 설정되지 않았습니다.",
                "[Mock] 서버 콘솔에서 GEMINI_API_KEY를 확인하세요.",
                "[Mock] KoBERT와 Vector DB는 정상 작동 중입니다."
            ]
        })
        return {
            "candidates": [{"content": {"parts": [{"text": mock_json_response}]}}]
        }

    # 2. 실제 API 호출 (httpx 사용)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # print(f"[Gemini] Calling API: {API_URL}") # 디버깅용 (필요시 주석 해제)
            response = await client.post(f"{API_URL}?key={API_KEY}", json=payload, headers=headers)
            
            # 404 등의 에러 발생 시 예외 발생
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            print(f"[Gemini API Error] Status: {e.response.status_code}, Response: {e.response.text}")
            # 모델을 찾을 수 없는 경우 (404) 등에 대한 처리 힌트 제공
            if e.response.status_code == 404:
                print("[Hint] 모델명이 잘못되었거나, 해당 API 키로 이 모델에 접근할 수 없습니다.")
            raise e
        except Exception as e:
            print(f"[Gemini Network Error] {e}")
            raise e


async def _get_paraphrasing_options_async(
    tag: str,
    original_sentence: str,
    user_preference: Dict[str, Any]
) -> List[str]:
    """
    Gemini에게 교정 옵션 생성을 요청하고 응답을 파싱합니다.
    """

    # 1. 프롬프트 구성
    system_instruction = (
        "당신은 한국어 문장 교정 전문가입니다. 다음 지침에 따라 입력된 문장을 교정하세요.\n"
        "1. [문맥 태그]와 [스타일]을 반영하여 어조를 조정하세요.\n"
        "2. 원본의 의미를 유지하되, 더 자연스럽고 명확하게 다듬으세요.\n"
        "3. 반드시 **3가지** 다른 버전의 교정안을 제안하세요.\n"
        "4. 응답은 오직 JSON 형식으로만 출력하세요. (key: 'options', value: list of strings)"
    )

    field = user_preference.get('field', 'general')
    intensity = user_preference.get('intensity', 'moderate')
    
    user_query = f"""
    [정보]
    - 문맥: {tag}
    - 스타일: {field}
    - 강도: {intensity}
    - 원문: "{original_sentence}"
    
    위 원문을 바탕으로 교정된 3가지 문장을 JSON으로 생성하세요.
    """

    # 2. Payload 구성
    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "options": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                }
            }
        }
    }

    try:
        # API 호출
        response = await call_gemini_api(payload)
        
        # 3. 응답 파싱
        if "candidates" not in response or not response["candidates"]:
            print("[Gemini] No candidates found in response.")
            return [original_sentence]

        json_text = response["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(json_text)
        
        return result.get("options", [original_sentence])
    
    except Exception as e:
        print(f"[Gemini Processing Error] {e}")
        # 실패 시 원문과 에러 메시지 반환 (사용자 피드백용)
        return [
            original_sentence,
            "(AI 응답 생성 실패)",
            "잠시 후 다시 시도해 주세요."
        ]


# Main.py에서 호출하는 진입점 함수
async def generate_correction(
    original_text: str,
    context_full: str,
    best_category: str,
    language: str,
    intensity: str,
    user_prompt: Optional[str],
    user_id: str
) -> Tuple[List[Dict[str, str]], str]:
    
    user_preference = {
        'field': best_category,
        'intensity': intensity,
        'language': language,
        'user_prompt': user_prompt 
    }

    try:
        corrected_texts = await _get_paraphrasing_options_async(
            tag=best_category,
            original_sentence=original_text,
            user_preference=user_preference
        )
    except Exception as e:
        print(f"[generate_correction] Critical Error: {e}")
        corrected_texts = [original_text]

    # 결과 포맷팅
    reco_options = [
        {"text": text, "category": best_category} for text in corrected_texts
    ]
    
    return reco_options, GEMINI_MODEL_VERSION