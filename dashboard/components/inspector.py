from __future__ import annotations

from typing import Optional

import streamlit as st

from queries import (
    get_asset_counts,
    get_cache_hit_rate,
    get_cost_estimate,
    get_latency_series,
    get_latency_summary,
    get_macro_cache_samples,
    get_macro_queue_length,
    get_recent_a_events,
    get_recent_runs,
)
from .charts import latency_line


def _render_latency(user_id: Optional[str]) -> None:
    summary = get_latency_summary(user_id=user_id)
    col1, col2 = st.columns(2)
    col1.metric("Avg Latency (ms)", f"{summary['avg']:.1f}")
    col2.metric("P95 Latency (ms)", f"{summary['p95']:.1f}")
    fig = latency_line(get_latency_series(user_id=user_id))
    st.plotly_chart(fig, use_container_width=True)


def _render_genai_run(user_id: Optional[str]) -> None:
    stats = get_cost_estimate(user_id=user_id)
    col1, col2 = st.columns(2)
    col1.metric("Estimated Cost", f"${stats['cost']:.4f}")
    col2.metric("Macro Queue (K diff>=0.1)", f"{stats['macro_queue']}")
    st.markdown("**Recent Runs (B)**")
    runs = get_recent_runs(user_id=user_id)
    if not runs:
        st.info("No recent runs available.")
        return
    for run in runs:
        ts = run.get("created_at")
        st.write(
            f"- [{ts}] {run.get('user_id', 'unknown')} → {run.get('target_category', 'n/a')} ({run.get('target_language', 'n/a')})"
        )


def _render_redis() -> None:
    hit_rate = get_cache_hit_rate()
    st.metric("Cache Hit Rate", f"{hit_rate:.1%}")
    st.markdown("**Macro Cache Samples (F)**")
    samples = get_macro_cache_samples()
    if not samples:
        st.info("No cache samples available.")
        return
    for item in samples:
        st.write(
            f"- {item.get('doc_id', 'doc')} | {item.get('macro_category_hint', 'n/a')} ({item.get('last_updated')})"
        )


def render_inspector(node_id: Optional[str], user_id: Optional[str]) -> None:
    st.markdown("### Inspector")
    if not node_id:
        st.info("Click a node to inspect metrics.")
        return

    if node_id in ("API", "Emb Model"):
        _render_latency(user_id)
    elif node_id == "GenAI (Run)":
        _render_genai_run(user_id)
    elif node_id in ("Redis", "GenAI (Macro)"):
        _render_redis()
    elif node_id == "Mongo":
        st.markdown("**Latest A Events (3)**")
        for ev in get_recent_a_events(limit=3, user_id=user_id):
            st.json(ev)
    elif node_id == "VectorDB":
        assets = get_asset_counts(user_id=user_id)
        st.metric("Context Blocks (E)", f"{assets.get('micro_contexts', 0):,}")
        st.info("Index Status: Ready")
    elif node_id == "Worker":
        st.info("Status: Processing")
        st.metric("Macro Queue (K diff>=0.1)", f"{get_macro_queue_length():,}")
    else:
        st.info(f"No detailed metrics mapped for {node_id}.")
