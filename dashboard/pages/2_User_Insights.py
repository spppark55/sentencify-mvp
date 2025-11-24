from __future__ import annotations

import pandas as pd
import streamlit as st

from queries import get_total_counts


def main():
    st.title("User Insights (Phase 3)")
    st.caption("Profiles and clusters. Falls back to mock data if collections are missing.")
    user_id = st.session_state.get("user_filter")

    try:
        totals = get_total_counts(user_id=user_id)
        st.metric("User Profiles (G)", f"{totals.get('G', 0):,}")
        st.metric("Clusters (J)", "Data pending")
        if totals.get("G", 0) == 0:
            raise RuntimeError("User profile data missing")
        st.success("User profile data available.")
    except Exception:
        st.warning("Data pending — showing mock cluster view.")
        mock = pd.DataFrame(
            [
                {"cluster": "A", "users": 10, "accept_rate": 0.42},
                {"cluster": "B", "users": 7, "accept_rate": 0.55},
            ]
        )
        st.dataframe(mock, use_container_width=True)


if __name__ == "__main__":
    main()
