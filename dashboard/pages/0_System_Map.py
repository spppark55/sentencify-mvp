from __future__ import annotations

import streamlit as st

from components.topology_graph import render_topology
from components.inspector import render_inspector
from queries import get_node_recency_map


def main():
    st.title("System Topology & LLMOps (Phase 1-1.5)")
    st.caption("Realtime view of infra + model components with recency heatmap.")
    user_id = st.session_state.get("user_filter")

    recency = get_node_recency_map(user_id=user_id)
    selected = render_topology(recency)
    if selected:
        st.session_state["selected_node"] = selected
    selected_node = st.session_state.get("selected_node")

    st.divider()
    render_inspector(selected_node, user_id)


if __name__ == "__main__":
    main()
