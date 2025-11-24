from __future__ import annotations

import streamlit as st

from queries import get_flow_counts


def main():
    st.title("Automation Impact & ROI (Phase 4)")
    st.caption("Tracks accept/lift. Falls back gracefully if data is missing.")
    user_id = st.session_state.get("user_filter")

    try:
        counts = get_flow_counts(user_id=user_id)
        accept_rate = (
            counts.get("C_accepts", 0) / counts.get("A", 1)
            if counts.get("A", 0) > 0
            else 0.0
        )
        st.metric("Accept Rate (C/A)", f"{accept_rate:.1%}")
        st.metric("Golden Data (H)", f"{counts.get('H', 0):,}")
    except Exception:
        st.warning("Data pending — showing mock ROI.")
        st.metric("Accept Rate (mock)", "42.0%")
        st.metric("Golden Data (mock)", "12")


if __name__ == "__main__":
    main()
