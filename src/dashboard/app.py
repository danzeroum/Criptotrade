"""Simple Streamlit dashboard placeholder."""
import streamlit as st

st.set_page_config(page_title="Crypto AI Trading Platform", layout="wide")

st.title("📊 Crypto AI Trading Platform")
st.write(
    "This is a placeholder dashboard. Future iterations will display portfolio metrics,"
    " open positions, and guardrail alerts."
)

st.metric(label="Sharpe Ratio (Paper)", value="--")
st.metric(label="Win Rate", value="--")
st.metric(label="Max Drawdown", value="--")
