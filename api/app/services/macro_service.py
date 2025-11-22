from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

from app.redis.client import set_macro_context
from app.schemas.macro import DocumentContextCache

load_dotenv()
_API_KEY = os.getenv("GEMINI_API_KEY")
if _API_KEY:
    genai.configure(api_key=_API_KEY)

_MODEL_NAME = "gemini-2.5-flash"
_model = genai.GenerativeModel(_MODEL_NAME)

_JSON_REGEX = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_payload(text: str) -> dict[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    match = _JSON_REGEX.search(cleaned)
    if not match:
        raise ValueError("LLM response did not contain JSON payload")
    return json.loads(match.group(0))


async def analyze_and_cache_macro_context(
    doc_id: str, full_text: str
) -> Optional[DocumentContextCache]:
    if not full_text or len(full_text) < 10:
        return None

    truncated_text = full_text[:3000]
    prompt = (
        "Analyze the following text and extract the 'macro_topic' (short summary, max 10 words) "
        "and 'macro_category_hint' (one of: thesis, email, report, article, marketing, customer_service).\n"
        'Return ONLY a valid JSON object: {"topic": "...", "category": "..."}\n'
        f"Text: {truncated_text}"
    )

    response = await _model.generate_content_async(prompt)
    payload = _extract_json_payload(response.text or "")
    topic = payload.get("topic")
    category = payload.get("category")
    if not topic or not category:
        raise ValueError("LLM response missing topic/category fields")

    now = datetime.now(timezone.utc)
    cache_object = DocumentContextCache(
        doc_id=doc_id,
        macro_topic=topic,
        macro_category_hint=category,
        macro_llm_version=_MODEL_NAME,
        cache_hit_count=0,
        last_updated=now,
        valid_until=now + timedelta(hours=1),
    )
    await set_macro_context(doc_id, cache_object)
    return cache_object
