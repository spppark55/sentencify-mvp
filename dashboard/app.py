import streamlit as st
import plotly.express as px

from queries import (
    get_total_traffic,
    get_micro_contexts_count,
    get_category_distribution,
    get_macro_etl_triggers,
    get_adaptive_weight_stats,
    get_cache_hit_rate,
    get_golden_data_count,
    get_acceptance_rate,
    get_user_profile_coverage,
)


st.set_page_config(
    page_title="Sentencify Analytics",
    page_icon="📊",
    layout="wide",
)

st.sidebar.title("Sentencify Dashboard")
st.sidebar.markdown(
    """
    **Phase 2 – Analytics**

    Use the navigation menu to explore metrics for each phase.
    """
)

st.title("Sentencify Analytics Overview")
st.caption("Consolidated KPIs across Phase 1 → Phase 2 pipelines.")

traffic = get_total_traffic()
micro_contexts = get_micro_contexts_count()
golden = get_golden_data_count()
accept_rate = get_acceptance_rate()
profiles = get_user_profile_coverage()

col1, col2, col3 = st.columns(3)
col1.metric("Total A Events", f"{traffic:,}")
col1.metric("Golden Data (H)", f"{golden:,}")
col2.metric("Micro Contexts (E)", f"{micro_contexts:,}")
col2.metric("User Profiles (G)", f"{profiles:,}")
col3.metric("Acceptance Rate", f"{accept_rate:.1%}")
col3.metric("Cache Hit Rate", f"{get_cache_hit_rate():.1%}")

st.divider()

st.subheader("Category Distribution (Phase 1)")
category_counts = get_category_distribution()
if category_counts:
    fig = px.pie(
        values=list(category_counts.values()),
        names=list(category_counts.keys()),
        hole=0.4,
        title="Recommendation Category Share",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No category data available.")

st.subheader("Macro ETL & Adaptive Weight")
col_a, col_b = st.columns(2)
macro_stats = get_macro_etl_triggers()
if macro_stats["total"]:
    ratio = macro_stats["triggered"] / macro_stats["total"]
else:
    ratio = 0.0
col_a.metric(
    "Diff ≥ 0.1 (Macro Trigger)",
    f"{macro_stats['triggered']}/{macro_stats['total']}",
    f"{ratio:.1%}",
)
alpha_stats = get_adaptive_weight_stats()
col_b.metric("Avg α", f"{alpha_stats['avg_alpha']:.2f}")
col_b.write(f"Min α: {alpha_stats['min_alpha']:.2f} | Max α: {alpha_stats['max_alpha']:.2f}")

st.success("Navigate to the Phase-specific pages via the sidebar for deeper insights.")
