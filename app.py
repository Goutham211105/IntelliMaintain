import streamlit as st
import pandas as pd
import plotly.express as px
from agent import IntelliMaintainAgent
from tools import generate_demo_data

st.set_page_config(page_title="IntelliMaintain", page_icon="🛠️", layout="wide")
st.title("🛠️ IntelliMaintain")
st.subheader("Agentic AI for Predictive Maintenance")
st.caption("A transparent, tool-using maintenance agent. Demo data is synthetic; results are decision-support only.")

with st.sidebar:
    st.header("Analysis settings")
    use_demo = st.toggle("Use built-in demo data", value=True)
    uploaded = st.file_uploader("Or upload sensor CSV", type=["csv"], disabled=use_demo)
    st.markdown("**Expected columns**")
    st.code("timestamp,vibration_mm_s,temperature_c,rpm,current_a")
    st.markdown("The agent can run without an API key or paid service.")

if use_demo:
    df = generate_demo_data()
elif uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
    except Exception as exc:
        st.error(f"Could not read CSV: {exc}")
        st.stop()
else:
    st.info("Choose demo data or upload a CSV file to begin.")
    st.stop()

st.markdown("### 1. Input data")
st.dataframe(df.tail(10), use_container_width=True)
numeric_cols = [c for c in ["vibration_mm_s", "temperature_c", "rpm", "current_a"] if c in df.columns]
if numeric_cols:
    metric = st.selectbox("Sensor to visualize", numeric_cols)
    x = "timestamp" if "timestamp" in df.columns else df.index
    chart_df = df.copy()
    if "timestamp" in chart_df.columns:
        chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"], errors="coerce")
        fig = px.line(chart_df, x="timestamp", y=metric, title=f"{metric} trend")
    else:
        fig = px.line(chart_df, y=metric, title=f"{metric} trend")
    st.plotly_chart(fig, use_container_width=True)

goal = st.text_input(
    "2. Give the agent a goal",
    value="Assess machine condition, investigate anomalies, and recommend maintenance actions."
)
run = st.button("Run agent analysis", type="primary")

if run:
    agent = IntelliMaintainAgent()
    with st.spinner("Agent is planning, selecting tools, evaluating results, and preparing a report..."):
        result = agent.run(df, goal=goal)
    st.markdown("### 3. Agent execution trace")
    for i, event in enumerate(result["trace"], start=1):
        with st.expander(f"Step {i}: {event['step']} — {event['status']}", expanded=(i == 1)):
            st.write(event["details"])
    st.markdown("### 4. Findings")
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall risk", result["assessment"]["risk_level"])
    c2.metric("Anomalies detected", result["assessment"]["anomaly_count"])
    c3.metric("Recommended action", result["assessment"]["recommended_action"])
    st.write(result["assessment"]["summary"])
    st.markdown("### Recommendations")
    for rec in result["assessment"]["recommendations"]:
        st.write(f"- {rec}")
    st.markdown("### Full report")
    st.text_area("Generated maintenance report", result["report"], height=260)
    st.download_button("Download report (.txt)", result["report"], file_name="intellimaintain_report.txt")
    st.info("This prototype uses transparent thresholds and synthetic/demo data. Validate thresholds against equipment-specific standards before real-world use.")
