#!/usr/bin/env python
"""
Phase 1.5 Integration Test – verifies diff → Macro ETL → Redis → adaptive scoring.

Prerequisite: API server running at http://localhost:8000 with Redis/Gemini configured.
Run: python scripts/phase1.5_test_integration.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
USER_ID = os.getenv("INTEGRATION_TEST_USER", "integration_tester")


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(f"{BASE_URL}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def _patch(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.patch(f"{BASE_URL}{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def run() -> None:
    print("[Integration] Creating document...")
    create_resp = _post("/documents", {"user_id": USER_ID})
    doc_id = create_resp["doc_id"]

    print("[Integration] Cold start recommend call...")
    cold_req = {
        "doc_id": doc_id,
        "user_id": USER_ID,
        "selected_text": "Short text",
        "context_prev": "",
        "context_next": "",
        "language": "ko",
        "intensity": "moderate",
    }
    cold_resp = _post("/recommend", cold_req)
    assert cold_resp["applied_weight_doc"] == 0.0, "Cold start alpha should be 0.0"

    long_text = (
        "This is a long integration test document about macro reasoning, AI governance, "
        "ethics, compliance, and adaptive contextual understanding. " * 10
    )
    print("[Integration] Updating document with long text to trigger Macro ETL...")
    _patch(f"/documents/{doc_id}", {"user_id": USER_ID, "latest_full_text": long_text})

    print("[Integration] Waiting for Macro ETL background task...")
    time.sleep(8)

    print("[Integration] Warm recommend call...")
    warm_req = {
        "doc_id": doc_id,
        "user_id": USER_ID,
        "selected_text": long_text[:400],
        "context_prev": long_text[400:600],
        "context_next": long_text[600:800],
        "language": "ko",
        "intensity": "moderate",
    }
    warm_resp = _post("/recommend", warm_req)
    assert warm_resp["applied_weight_doc"] > 0.0, "Adaptive alpha should be > 0 after long text"
    assert warm_resp["P_doc"], "P_doc must reflect cached macro context"

    print("✅ Phase 1.5 Integration Test Passed")


if __name__ == "__main__":
    run()
