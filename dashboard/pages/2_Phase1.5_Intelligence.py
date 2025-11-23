import streamlit as st
import plotly.express as px

from queries import (
    get_macro_stats,
    get_macro_etl_triggers,
    get_adaptive_weight_stats,
    get_cache_hit_rate,
)


st.set_page_config(page_title="Phase 1.5 – Macro Intelligence", page_icon="🧠")

st.title("Phase 1.5 – Macro Intelligence")
st.caption("Diff-based Gatekeeper telemetry and adaptive scoring insights.")

macro_trigger = get_macro_etl_triggers()
alpha_stats = get_adaptive_weight_stats()

col1, col2, col3 = st.columns(3)
trigger_ratio = (
    macro_trigger["triggered"] / macro_trigger["total"] if macro_trigger["total"] else 0.0
)
col1.metric("Macro ETL Triggers", f"{macro_trigger['triggered']}", f"{trigger_ratio:.1%}")
col2.metric("Avg Adaptive Weight (α)", f"{alpha_stats['avg_alpha']:.2f}")
col2.write(f"Range: {alpha_stats['min_alpha']:.2f} – {alpha_stats['max_alpha']:.2f}")
col3.metric("Redis Cache Hit Rate", f"{get_cache_hit_rate():.1%}")

st.divider()

st.subheader("Diff Ratio Histogram")
macro_stats = get_macro_stats()
if macro_stats["diffs"]:
    hist_fig = px.histogram(
        x=macro_stats["diffs"],
        nbins=30,
        labels={"x": "Diff Ratio", "y": "Documents"},
        title="Document Diff Ratio Distribution",
    )
    st.plotly_chart(hist_fig, use_container_width=True)
else:
    st.info("No diff ratio data available.")

st.divider()

st.info("Drafting vs Polishing split, macro-topic caching metrics, and other insights can be expanded here.")
