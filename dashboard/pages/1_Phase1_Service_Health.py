import streamlit as st
import plotly.express as px

from queries import (
    get_total_traffic,
    get_micro_contexts_count,
    get_category_distribution,
    get_acceptance_rate,
)


st.set_page_config(page_title="Phase 1 – Service Health", page_icon="⚙️")

st.title("Phase 1 – Service Health")
st.caption("Operational telemetry for the recommendation & paraphrasing APIs.")

col1, col2, col3 = st.columns(3)
col1.metric("Total A Events", f"{get_total_traffic():,}")
col2.metric("Micro Contexts Captured", f"{get_micro_contexts_count():,}")
col3.metric("User Acceptance Rate", f"{get_acceptance_rate():.1%}")

st.divider()

st.subheader("Recommendation Category Mix")
category_data = get_category_distribution()
if category_data:
    fig = px.bar(
        x=list(category_data.keys()),
        y=list(category_data.values()),
        labels={"x": "Category", "y": "Events"},
        title="Distribution of Recommended Categories",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No recommendation category data available.")

# [임시 디버깅] Raw Data 5개만 찍어보기
st.subheader("🔍 Debug: Raw LogA Data")
raw_data = list(db.log_a_recommend.find({}, {"reco_options": 1, "reco_category_input": 1}).limit(5))
st.write(raw_data)  # 화면에 JSON 그대로 출력됨

st.divider()

st.info("Additional Phase 1 metrics (latency, Kafka health, etc.) can be layered here as needed.")
