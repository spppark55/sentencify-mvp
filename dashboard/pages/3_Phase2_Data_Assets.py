import streamlit as st
import plotly.express as px

from queries import (
    get_golden_data_count,
    get_user_profile_coverage,
    get_acceptance_rate,
)


st.set_page_config(page_title="Phase 2 – Data Assets", page_icon="🧱")

st.title("Phase 2 – Data Assets")
st.caption("Monitoring high-quality data assets that feed downstream training.")

col1, col2, col3 = st.columns(3)
col1.metric("Golden Training Examples (H)", f"{get_golden_data_count():,}")
col2.metric("User Profiles (G)", f"{get_user_profile_coverage():,}")
col3.metric("Acceptance Rate (C)", f"{get_acceptance_rate():.1%}")

st.divider()

st.subheader("Data Quality Roadmap")
st.write(
    """
    - **Golden Data**: High-consistency training examples ready for fine-tuning.
    - **User Profiles**: Captures long-term behavior and preferences per user.
    - **Correction Funnel**: Acceptance rate approximates the conversion of recommendations to final selections.
    """
)

st.info("Phase 3/4 placeholders can be linked here once their metrics become available.")
