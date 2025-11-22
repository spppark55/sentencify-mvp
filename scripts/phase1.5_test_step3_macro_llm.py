#!/usr/bin/env python
"""
Standalone verification for Phase 1.5 Step 3 (Macro ETL using Gemini mock).

Run: python scripts/test_step3_macro_llm.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")

from app.redis.client import get_macro_context, get_redis_client  # noqa: E402
from app.services.macro_service import analyze_and_cache_macro_context  # noqa: E402


async def main() -> None:
    doc_id = "test-doc-step3"
    full_text = "This is a long enough text about AI ethics and compliance in organizations."

    client = get_redis_client()
    await client.delete(f"macro_context:{doc_id}")

    mock_payload = SimpleNamespace(text='{"topic": "AI Ethics", "category": "thesis"}')

    with patch(
        "app.services.macro_service._model.generate_content_async",
        new=AsyncMock(return_value=mock_payload),
    ):
        result = await analyze_and_cache_macro_context(doc_id, full_text)

    assert result is not None, "Service should return a DocumentContextCache object."
    assert result.macro_topic == "AI Ethics"
    assert result.macro_category_hint == "thesis"

    cached = await get_macro_context(doc_id)
    assert cached is not None, "Redis should store the macro context."
    assert cached.macro_topic == "AI Ethics"
    assert cached.macro_category_hint == "thesis"

    print("✅ Step 3 Macro ETL Service Passed")


if __name__ == "__main__":
    asyncio.run(main())
