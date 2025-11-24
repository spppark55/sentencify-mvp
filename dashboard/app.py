from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import streamlit as st

from queries import get_recent_a_events, get_system_health


st.set_page_config(
    page_title="Sentencify Control Tower",
    page_icon="🛰️",
    layout="wide",
)


def _fmt_health(name: str, status: bool) -> str:
    return f"{'🟢' if status else '🔴'} {name}"


def _render_health() -> None:
    health = get_system_health()
    st.sidebar.markdown("### System Health")
    st.sidebar.write(_fmt_health("MongoDB", health["mongo"]))
    st.sidebar.write(_fmt_health("Redis", health["redis"]))
    st.sidebar.write(_fmt_health("VectorDB", health["vector"]))


def _render_ticker(user_id: Optional[str]) -> None:
    st.sidebar.markdown("### Live Ticker (A)")
    events = get_recent_a_events(limit=5, user_id=user_id)
    if not events:
        st.sidebar.info("No recent A events.")
        return
    for ev in events:
        ts = ev.get("created_at")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%H:%M:%S")
        else:
            ts_str = "--:--:--"
        uid = ev.get("user_id", "unknown")
        cat = ev.get("reco_category_input", "n/a")
        latency = ev.get("latency_ms")
        latency_str = f"{latency:.0f}ms" if latency is not None else "--"
        st.sidebar.write(f"[{ts_str}] {uid} : {cat} ({latency_str})")


def _sidebar_controls() -> Optional[str]:
    st.sidebar.title("Sentencify v2.4 Control Tower")
    user_id = st.sidebar.text_input("User ID Filter (optional)")
    st.session_state["user_filter"] = user_id or None

    auto = st.sidebar.toggle("Auto-Refresh (5s)", value=False)
    if auto:
        time.sleep(5)
        st.experimental_rerun()

    _render_health()
    _render_ticker(user_id or None)
    return user_id or None


def main() -> None:
    user_id = _sidebar_controls()
    st.title("Sentencify Dashboard")
    st.caption("Sidecar Streamlit dashboard — Read-only control tower for v2.4.")
    st.info(
        "Use the sidebar to filter by user_id and enable auto-refresh. "
        "Navigate pages via the left navigation."
    )
    st.write(f"Active user filter: `{user_id or 'None'}`")


if __name__ == "__main__":
    main()
