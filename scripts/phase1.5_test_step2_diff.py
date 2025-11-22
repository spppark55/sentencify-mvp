#!/usr/bin/env python
"""
Standalone verification for Phase 1.5 Step 2 (diff ratio calculator).

Run: python scripts/test_step2_diff.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
API_DIR = ROOT_DIR / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.utils.diff import calculate_diff_ratio  # noqa: E402


def _approx_equal(a: float, b: float, eps: float = 1e-6) -> bool:
    return abs(a - b) <= eps


def run_tests() -> None:
    case1 = calculate_diff_ratio("Hello", "Hello")
    assert _approx_equal(case1, 0.0), f"Expected 0.0, got {case1}"

    case2 = calculate_diff_ratio("Hello", "Hello World")
    assert case2 > 0.0, "Expected diff > 0 for appended text"

    case3 = calculate_diff_ratio("", "New")
    assert case3 == 1.0, f"Expected 1.0 due to normalization, got {case3}"

    print("✅ Step 2 Diff Logic Passed")


if __name__ == "__main__":
    run_tests()
