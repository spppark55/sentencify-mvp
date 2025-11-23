#!/usr/bin/env python
"""
Standalone verification for Phase 1.5 Step 4 (Adaptive scoring logic).

Run: python scripts/test_step4_scoring.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.utils.scoring import calculate_alpha, calculate_maturity_score  # noqa: E402


def blend_scores(p_vec: dict[str, float], p_doc: dict[str, float], alpha: float) -> dict[str, float]:
    final = {}
    for cat in set(p_vec) | set(p_doc):
        final[cat] = (1 - alpha) * p_vec.get(cat, 0.0) + alpha * p_doc.get(cat, 0.0)
    return final


def run_tests() -> None:
    maturity_short = calculate_maturity_score(10)
    alpha_short = calculate_alpha(maturity_short)
    assert maturity_short == 0.0 and alpha_short == 0.0, "Short text should yield zero alpha"

    maturity_long = calculate_maturity_score(500)
    alpha_long = calculate_alpha(maturity_long)
    assert maturity_long == 1.0, "Length 500 should be fully mature"
    assert abs(alpha_long - 0.4) < 1e-6, "Alpha should equal base alpha when mature"

    p_vec = {"email": 0.8}
    p_doc = {"thesis": 1.0}
    alpha = 0.4
    final_scores = blend_scores(p_vec, p_doc, alpha)
    assert abs(final_scores["email"] - 0.48) < 1e-6, "Email score mismatch"
    assert abs(final_scores["thesis"] - 0.4) < 1e-6, "Thesis score mismatch"

    print("✅ Step 4 Scoring Logic Passed")


if __name__ == "__main__":
    run_tests()
