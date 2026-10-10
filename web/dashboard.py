import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.db_manager import connect, init_db  # noqa: E402

st.set_page_config(page_title="AI Interviewer: reports", layout="wide")
st.title("Interview reports")


def load_data() -> pd.DataFrame:
    init_db()
    with connect() as conn:
        return pd.read_sql_query(
            "SELECT id, user_id, created_at, knowledge, logic, clarity, overall, report_text "
            "FROM reports ORDER BY created_at DESC",
            conn,
        )


if st.sidebar.button("Refresh"):
    st.rerun()

df = load_data()

if df.empty:
    st.info("No reports yet. Finish an interview through the Discord bot or cli.py first.")
    st.stop()

scored = df.dropna(subset=["overall"])
c1, c2, c3 = st.columns(3)
c1.metric("Interviews", len(df))
c2.metric("Mean overall score", f"{scored['overall'].mean():.1f}" if len(scored) else "n/a")
c3.metric("Reports with unparsed scores", len(df) - len(scored))

st.subheader("All interviews")
st.dataframe(df.drop(columns="report_text"), use_container_width=True, hide_index=True)

if len(scored):
    st.subheader("Mean score per dimension (share of maximum)")
    means = pd.Series({
        "Knowledge (/40)": scored["knowledge"].mean() / 40,
        "Logic (/30)": scored["logic"].mean() / 30,
        "Clarity (/30)": scored["clarity"].mean() / 30,
    })
    st.bar_chart(means)

st.subheader("Full report")
selected = st.selectbox("Interview id", df["id"].tolist())
st.markdown(df.loc[df["id"] == selected, "report_text"].iloc[0])
