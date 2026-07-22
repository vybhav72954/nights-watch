"""Night's Watch demo -- entry point. Run from the repo root:

    streamlit run app/streamlit_app.py

Fully functional with no API key and no internet (rules-floor classifier,
inlined graph assets). Spec: docs/APP_DESIGN.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "app")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

import ui
from src.detector import active_classifier_path  # importing runs load_dotenv() (B8)

st.set_page_config(page_title="Night's Watch", page_icon="🛡️", layout="wide")

st.session_state.setdefault("live_reports", [])
st.session_state.setdefault("chat_messages", [])
st.session_state.setdefault("last_join", None)

page = st.navigation(
    [
        st.Page("app_pages/live.py", title="Live",
                icon=":material/sensors:", default=True),
        st.Page("app_pages/command_centre.py", title="Command centre",
                icon=":material/hub:"),
        st.Page("app_pages/counterfeit.py", title="Counterfeit",
                icon=":material/payments:"),
        st.Page("app_pages/replay.py", title="Lead time",
                icon=":material/schedule:"),
    ],
    position="top",
)

with st.sidebar:
    ui.inject_css()
    _llm = active_classifier_path() == "llm"
    ui.sidebar_brand(
        "LLM (Groq) · rules fallback" if _llm else "Rules floor · offline, deterministic",
        live=_llm,
    )

    # Sidebar code runs before page.run(), so clearing here renders this same
    # run as a fresh session without restarting Streamlit. Seeded state is
    # cached and untouched.
    if st.button("Reset session", icon=":material/restart_alt:", width="stretch"):
        st.session_state.live_reports = []
        st.session_state.chat_messages = []
        st.session_state.last_join = None
    if st.session_state.live_reports:
        st.caption(f"{len(st.session_state.live_reports)} live report(s) this session")

page.run()
