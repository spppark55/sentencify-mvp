# pip install python-dotenv google-generativeai openai

import time
from statistics import mean

import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv
import os


PROMPT = """당신은 전문 교정 전문가입니다. 아래 지침에 따라 문장을 교정해 주세요.
**교정 분야**: general
- 일반적인 문장 스타일로, 명확하고 자연스럽게 교정하세요.
**교정 강도**: weak
- 문장의 흐름과 명확성을 개선하세요. 어색한 표현을 자연스럽게 다듬고, 가독성을 높이세요.
**언어**: 한국어로 작성
**추가 요청**: 없음
**문맥 정보**:
- 이전 문장: 없음
- 다음 문장: 없음
**중요 규칙**:
1. 반드시 교정된 문장 3개만 생성하세요
2. 각 문장은 줄바꿈으로만 구분합니다
3. 번호, 불릿, 설명문, 서문 등은 일절 포함하지 마세요
4. 각 버전은 서로 다른 접근 방식이나 뉘앙스를 가져야 합니다
5. 원문의 핵심 의미는 반드시 유지하세요
---
**원본 문장**: 예시 문장입니다. 품질 비교 테스트용으로 작성되었습니다.
---
교정된 문장 3개:"""


def measure_gemini(prompt: str, iterations: int = 1):
    """Gemini 응답 시간 + 응답 내용 반환"""
    gemini_times = []
    responses = []
    model = genai.GenerativeModel("models/gemini-2.5-flash")

    for _ in range(iterations):
        start = time.perf_counter()
        response = model.generate_content(prompt)
        text = response.text
        elapsed = time.perf_counter() - start

        gemini_times.append(elapsed)
        responses.append(text)

    return mean(gemini_times), responses


def measure_openai(prompt: str, iterations: int = 1):
    """OpenAI 응답 시간 + 응답 내용 반환"""
    client = OpenAI()
    openai_times = []
    responses = []

    for _ in range(iterations):
        start = time.perf_counter()
        response = client.responses.create(
            model="gpt-4.1-nano",
            input=prompt,
        )
        text = response.output_text
        elapsed = time.perf_counter() - start

        openai_times.append(elapsed)
        responses.append(text)

    return mean(openai_times), responses


def main():
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")

    print("⏳ Gemini 테스트 중...")
    gemini_avg, gemini_responses = measure_gemini(PROMPT)

    print("⏳ OpenAI 테스트 중...")
    openai_avg, openai_responses = measure_openai(PROMPT)

    print("\n===== 📊 결과 비교 =====")
    print(f"Gemini 평균 응답 시간: {gemini_avg:.3f} 초")
    print(f"OpenAI 평균 응답 시간: {openai_avg:.3f} 초")

    print("\n===== ✨ Gemini 응답 =====")
    for i, resp in enumerate(gemini_responses):
        print(f"\n--- Gemini 응답 #{i+1} ---\n{resp}")

    print("\n===== 🤖 OpenAI 응답 =====")
    for i, resp in enumerate(openai_responses):
        print(f"\n--- OpenAI 응답 #{i+1} ---\n{resp}")


if __name__ == "__main__":
    main()
