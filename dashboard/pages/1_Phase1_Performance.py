import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from queries.mongo import (
    get_conversion_funnel,
    get_rule_vs_vector_stats,
    get_latency_breakdown,
    get_user_intent_stats
)

def main():
    st.title("Phase 1 Performance & Engagement")
    st.caption("Focus: Funnel Conversion, Hybrid Engine Balance, Latency, User Intent")
    
    user_id = st.session_state.get("user_filter")
    if user_id:
        st.info(f"Filtering data for User: {user_id}")

    # --- Section 1: Paraphrasing Funnel ---
    st.header("📉 Paraphrasing Funnel")
    funnel_data = get_conversion_funnel(user_id)
    
    fig_funnel = go.Figure(go.Funnel(
        y=["View (Recommend)", "Run (Paraphrase)", "Accept (Select)"],
        x=[funnel_data["view"], funnel_data["run"], funnel_data["accept"]],
        textposition="inside",
        textinfo="value+percent initial",
        opacity=0.65, 
        marker={"color": ["#636EFA", "#EF553B", "#00CC96"]}
    ))
    fig_funnel.update_layout(margin=dict(t=20, b=20))
    st.plotly_chart(fig_funnel, use_container_width=True)
    
    col1, col2, col3 = st.columns(3)
    v, r, a = funnel_data["view"], funnel_data["run"], funnel_data["accept"]
    ctr_run = (r / v * 100) if v > 0 else 0
    ctr_accept = (a / r * 100) if r > 0 else 0
    
    col1.metric("View Count", v)
    col2.metric("View → Run Rate", f"{ctr_run:.1f}%")
    col3.metric("Run → Accept Rate", f"{ctr_accept:.1f}%")

    st.divider()

    # --- Section 2: Hybrid Engine Balance ---
    st.header("⚖️ Hybrid Engine Balance (Rule vs Vector)")
    
    hybrid_stats = get_rule_vs_vector_stats(user_id)
    
    c1, c2 = st.columns([1, 3])
    with c1:
        st.metric("Rule Trigger Rate", f"{hybrid_stats['rule_trigger_rate']*100:.1f}%", help="% of requests where Rule Engine contributed > 0 score")
        st.markdown("""
        **Analysis:**
        - High correlation suggests Rule/Vector agree.
        - Points on axes imply one engine dominating.
        """)
        
    with c2:
        if hybrid_stats["scatter_data"]:
            df_scatter = pd.DataFrame(hybrid_stats["scatter_data"])
            fig_scatter = px.scatter(
                df_scatter, x="x", y="y", 
                labels={"x": "Vector Score (P_vec)", "y": "Rule Score (P_rule)"},
                title="Score Correlation (Sampled)",
                opacity=0.6
            )
            # Add diagonal line for visual reference
            fig_scatter.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(color="Red", dash="dash"))
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("No scoring data available.")

    st.divider()

    # --- Section 3: System Latency ---
    st.header("⚡ System Latency (SLA: 300ms)")
    
    lat_stats = get_latency_breakdown(user_id)
    
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("P50 Latency", f"{lat_stats['p50']:.0f}ms")
    l2.metric("P95 Latency", f"{lat_stats['p95']:.0f}ms", delta_color="inverse", delta=f"{lat_stats['p95']-300:.0f}ms vs SLA" if lat_stats['p95'] > 300 else None)
    l3.metric("P99 Latency", f"{lat_stats['p99']:.0f}ms")
    
    if lat_stats["trend"]:
        df_trend = pd.DataFrame(lat_stats["trend"])
        fig_trend = px.line(df_trend, x="timestamp", y="latency", title="Latency Trend over Time")
        fig_trend.add_hline(y=300, line_dash="dot", line_color="red", annotation_text="SLA (300ms)")
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("No latency data available.")

    st.divider()

    # --- Section 4: User Intent ---
    st.header("🏷️ User Intent Analysis")
    
    intent_stats = get_user_intent_stats(user_id)
    
    i1, i2 = st.columns(2)
    
    with i1:
        st.subheader("Top Categories")
        cats = intent_stats["categories"]
        if cats:
            fig_cat = px.pie(names=list(cats.keys()), values=list(cats.values()), hole=0.4)
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No category data.")
            
    with i2:
        st.subheader("Preferred Intensity")
        ints = intent_stats["intensities"]
        if ints:
            fig_int = px.bar(x=list(ints.keys()), y=list(ints.values()), labels={"x": "Intensity", "y": "Count"})
            st.plotly_chart(fig_int, use_container_width=True)
        else:
            st.info("No intensity data.")

if __name__ == "__main__":
    main()
