"""Beat 1 -- the citizen sensor: paste a message, get a verdict + guidance.
Every submission becomes a structured report that joins the live graph."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import core
from src.detector import detect, guidance
from src.evidence import DEMO_HUB_DEGREE_CAP

# staged hero (verified: joins ring R0000, 4 -> 5) + a legit decoy (verified: not scam)
HERO = (
    "URGENT: This is CBI. A parcel in your name has illegal items. "
    "You are under digital arrest. Pay 50000 to mule00@okaxis immediately "
    "from +919876543210 or face arrest."
)
DECOY = "Hey, just reached home. I'll pay you back the 500 tomorrow, thanks!"
# plain-string labels on purpose: icon-prefixed pill options don't round-trip
# through AppTest, and the hero pill is the one on-stage interaction that must
# stay machine-verifiable
SUGGESTIONS = {
    "⚖️ A digital-arrest scam (demo)": HERO,
    "✅ A normal message": DECOY,
}

st.title("Check a suspicious message")
st.caption(
    "Paste any SMS / WhatsApp forward / call transcript. Consent-first: "
    "only what you paste is analysed — nothing is tapped or tracked."
)


def _process(text: str) -> None:
    live = st.session_state.live_reports
    _, _, rings_before = core.current_state(DEMO_HUB_DEGREE_CAP, live)
    with st.spinner("Analysing…"):
        report = detect(text, channel="whatsapp")
    live.append(report)
    _, _, rings_after = core.current_state(DEMO_HUB_DEGREE_CAP, live)

    joined = core.ring_containing(rings_after, report.report_id)
    n_similar = joined.size - 1 if joined else None
    advice = guidance(report, similar_reports_count=n_similar)
    if joined:
        sizes_before = {r.ring_id: r.size for r in rings_before}
        st.session_state.last_join = {
            "ring_id": joined.ring_id,
            "before": sizes_before.get(joined.ring_id, 0),
            "after": joined.size,
        }
    st.session_state.chat_messages.append({"role": "user", "text": text})
    st.session_state.chat_messages.append({
        "role": "assistant",
        "report": report.for_model_input(),  # gt-safe, always (hard rule §2.2)
        "advice": advice,
        "joined_ring_id": joined.ring_id if joined else None,
        "ring_size": joined.size if joined else None,
    })


def _render_verdict(msg: dict) -> None:
    v = msg["report"]["verdict"]
    if v["is_scam"]:
        st.error(
            f"🚨 **Scam — {v['scam_type'].replace('_', ' ')}** · "
            f"confidence {v['confidence']:.2f}"
        )
    else:
        st.success(f"✅ **No strong scam signals** · confidence {v['confidence']:.2f}")
    if v["red_flags"]:
        st.markdown(" ".join(f":red-badge[{f.replace('_', ' ')}]" for f in v["red_flags"]))
    st.write(msg["advice"])

    ents = msg["report"]["entities"]
    rows = [
        (field.replace("_", " "), ", ".join(map(str, val)) if isinstance(val, list) else str(val))
        for field, val in ents.items()
        if val or val == 0
    ]
    if rows:
        st.dataframe(
            pd.DataFrame(rows, columns=["identifier", "value"]),
            hide_index=True,
        )
    if msg["joined_ring_id"]:
        st.warning(
            f"⚠ Matches known ring **{msg['joined_ring_id']}** — now "
            f"**{msg['ring_size']} linked incidents**. Open the Command centre."
        )


for msg in st.session_state.chat_messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["text"])
    else:
        with st.chat_message("assistant", avatar="🛡️"):
            _render_verdict(msg)

if not st.session_state.chat_messages:
    selected = st.pills("Try one:", list(SUGGESTIONS), label_visibility="collapsed")
    if selected:
        _process(SUGGESTIONS[selected])
        st.rerun()

if prompt := st.chat_input("Paste the suspicious message…"):
    _process(prompt)
    st.rerun()
