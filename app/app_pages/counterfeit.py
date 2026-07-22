"""Counterfeit currency: circulation intelligence -- the FICN re-point of the
Detect->Link->Prove spine (CLAUDE.md §3 row 1).

Honest scope, stated on screen: no note-image CV / accuracy number is claimed
here (a real "accuracy across denominations and print quality" figure needs a
labelled genuine-vs-fake image corpus we will not fabricate). What is
demonstrated is the *intelligence* half of the brief -- seizures sharing a reused
printing-plate serial cluster into a circulation ring (Layer 1, deterministic),
the courier account laundering proceeds across several print operations surfaces
as the Layer 2 kingpin, and the SAME hash-stamped, BSA §63 evidence pack is
emitted -- proven against a planted answer key, exactly as the scam side is.

Every value shown is a `src.counterfeit` or `src` call; no ground truth is read.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import altair as alt
import core
import counterfeit_core as ccore
import pandas as pd
import streamlit as st
import ui
from src.evidence import build_evidence_pack, build_kingpin_leads
from src.graph import rank_kingpins

ui.inject_css()
ui.page_header(
    "Circulation intelligence · FICN",
    "Counterfeit currency",
    "Fake-currency circulation intelligence: the same Detect → Link → Prove spine, "
    "re-pointed to seizure records.",
)

ui.scope_note(
    "<b>What this is.</b> Seizures that share a reused printing-plate serial are "
    "clustered into a circulation ring (Layer 1, deterministic); the courier "
    "account laundering proceeds across several print operations surfaces as the "
    "Layer 2 kingpin. The same hash-stamped, court-admissible (BSA §63) evidence "
    "pack is produced, byte-for-byte the machinery the scam side uses.<br>"
    "<b>What it is not.</b> This is not a note-image counterfeit classifier. A real "
    "accuracy figure across denominations and print quality needs a labelled "
    "genuine-vs-fake image dataset, which we will not fabricate, so it is stated "
    "as out of scope rather than faked. This is the circulation-network half."
)

ui.layer_cards()


def _cap_label(c: int | None) -> str:
    return "uncapped" if c is None else str(c)


cap = st.select_slider(
    "Hub degree cap: the live precision/recall threshold. Layer 1 ignores any "
    "identifier (serial or account) touched by more seizures than this (fan-in ≠ proof).",
    options=ccore.FICN_CAPS,
    value=ccore.FICN_HUB_DEGREE_CAP,
    format_func=_cap_label,
)

seizures, g, rings = ccore.seizure_state(cap)
by_id = {s.report_id: s for s in seizures}
scores = rank_kingpins(g, rings) if rings else []
leads = build_kingpin_leads(scores, rings, top_k=5) if scores else []
top_node = leads[0].node if leads else None

tab_net, tab_king, tab_ev, tab_val = st.tabs(
    [":material/hub: Circulation network", ":material/star: Kingpin",
     ":material/description: Evidence", ":material/verified: Validation"]
)

with tab_net:
    ring_fv = ccore.ring_face_value(rings[0], by_id) if rings else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Circulation rings", len(rings))
    c2.metric("Largest ring", rings[0].size if rings else 0)
    c3.metric("Seizures in graph", len(seizures))
    c4.metric("Face value, largest ring", core.rupees(ring_fv))

    html, n_hidden = ccore.seizure_graph_html(cap, top_node)
    st.iframe(html, height=580)
    st.caption(
        "▲ colour = reused plate serial (the ring link) · ⬤ colour = courier account · "
        "⬤ grey = seizure · ◆ orange = high fan-in, excluded by the cap · "
        "★ red = Layer-2 kingpin lead. "
        f"{n_hidden} isolated genuine-note recoveries not drawn (no ring membership)."
    )

    # Circulation at a glance: descriptive stats of the seized base, straight off
    # the SeizureRecord fields (no ground truth read). Two honest reads -- what
    # note class carries the fake face value, and where it enters -- neither of
    # which is a Layer 1 link (a denomination and a corridor are context, never a
    # graph node), so they colour in the story without over-claiming.
    st.markdown("**Circulation at a glance**")
    _DENOM_COLORS = {100: "#a3e635", 200: "#f472b6", 500: "#38bdf8", 2000: "#a78bfa"}
    face_by_denom: dict[int, int] = {}
    count_by_denom: dict[int, int] = {}
    count_by_point: dict[str, int] = {}
    for s in seizures:
        face_by_denom[s.denomination] = face_by_denom.get(s.denomination, 0) + s.face_value
        count_by_denom[s.denomination] = count_by_denom.get(s.denomination, 0) + 1
        count_by_point[s.seizure_point] = count_by_point.get(s.seizure_point, 0) + 1

    gc1, gc2 = st.columns([5, 6], gap="medium")
    with gc1:
        denoms = sorted(face_by_denom)
        dd = pd.DataFrame(
            [{"denom": f"₹{k}", "face": face_by_denom[k],
              "seizures": count_by_denom[k]} for k in denoms]
        )
        # Theta is the seizure COUNT, not face value: by volume Rs 500 dominates
        # (as in real FICN), but by face value the Rs 2000 note leads, since its
        # per-note value is 4x -- so a face-value donut would contradict the
        # caption. Face value stays in the tooltip for the fuller picture.
        donut = alt.Chart(dd).mark_arc(innerRadius=46, cornerRadius=3).encode(
            theta=alt.Theta("seizures:Q", stack=True),
            color=alt.Color(
                "denom:N",
                sort=[f"₹{k}" for k in denoms],
                scale=alt.Scale(domain=[f"₹{k}" for k in denoms],
                                range=[_DENOM_COLORS.get(k, "#8696a0") for k in denoms]),
                legend=alt.Legend(orient="bottom", title=None),
            ),
            tooltip=[
                alt.Tooltip("denom:N", title="denomination"),
                alt.Tooltip("seizures:Q", title="seizures"),
                alt.Tooltip("face:Q", title="face value (Rs)", format=","),
            ],
        )
        st.altair_chart(ui.style_chart(donut, height=230))
        st.caption("Share of seizures by note class. ₹500 dominates by volume, "
                   "as in real FICN seizures.")
    with gc2:
        gd = pd.DataFrame(
            [{"corridor": k, "seizures": v} for k, v in count_by_point.items()]
        )
        bar = alt.Chart(gd).mark_bar(cornerRadiusEnd=4, color="#4fd1c5", height=16).encode(
            x=alt.X("seizures:Q", title="seizures"),
            y=alt.Y("corridor:N", sort="-x", title=None),
            tooltip=[alt.Tooltip("corridor:N", title="entry corridor"),
                     alt.Tooltip("seizures:Q")],
        )
        st.altair_chart(ui.style_chart(bar, height=230))
        st.caption("Seizures by entry corridor (context only: a location is never a "
                   "graph node; linking on a busy corridor would forge false edges).")

with tab_king:
    st.subheader("Layer 2: the launderer, a lead not proof")
    st.caption(
        "The account banking proceeds from several print operations is the "
        "cross-ring bridge. Too many seizures touch it for Layer 1 to link on it "
        "(fan-in ≠ proof, the same guardrail that protects a busy merchant), so it "
        "surfaces here by centrality."
    )
    if not leads:
        st.info("No rings at this cap, so no kingpin lead to rank.")
    for i, lead in enumerate(leads, start=1):
        with st.container(border=True):
            st.markdown(f"**#{i} · `{lead.node}`** · centrality score {lead.score:.3f}")
            st.markdown(
                f"Bridges **{len(lead.bridged_ring_ids)}** circulation ring(s) "
                f"({', '.join(lead.bridged_ring_ids)}) · "
                f"{lead.bridged_incident_count} linked seizures"
            )
            st.write(lead.narrative)
            st.caption(lead.disclaimer)  # always rendered in full (hard rule §2.5)

with tab_ev:
    st.subheader("Layer 1: the auditable evidence pack")
    if not rings:
        st.info("No rings at this cap, so nothing to build a pack for.")
    else:
        ring_id = st.selectbox("Ring", [r.ring_id for r in rings])
        ring = next(r for r in rings if r.ring_id == ring_id)
        # incident_noun re-points the pack's prose to "seizure records"; the
        # methodology parameters come off the ring itself (B22), so moving the
        # slider can never desync the pack from how its ring was found.
        pack = build_evidence_pack(ring, g, by_id, incident_noun="seizure records")

        st.markdown(f"Pack integrity hash (SHA-256): `{pack.content_sha256}`")
        pdf_path = (Path(tempfile.gettempdir())
                    / f"nightswatch_ficn_{ring_id}_{pack.content_sha256[:8]}.pdf")
        if not pdf_path.exists():
            pack.to_pdf(pdf_path)
        d1, d2 = st.columns(2)
        d1.download_button(
            ":material/download: Evidence pack (JSON)",
            data=json.dumps(pack.to_dict(), indent=2, default=str),
            file_name=f"ficn_evidence_{ring_id}.json",
            mime="application/json",
        )
        d2.download_button(
            ":material/download: Evidence pack (PDF)",
            data=pdf_path.read_bytes(),
            file_name=f"ficn_evidence_{ring_id}.pdf",
            mime="application/pdf",
        )
        st.markdown(pack.to_markdown())

with tab_val:
    st.subheader("Does it actually work? The answer-key numbers")
    st.caption(
        "Validation runs on a seeded network with a planted answer key (ring "
        "membership + which account is the launderer), so recovery can be proved, "
        "not asserted. Read from the code-produced artifact, never typed in."
    )
    val = core.processed_artifact("ficn_validation")
    if val:
        ms = val["multi_seed"]
        v1, v2, v3 = st.columns(3)
        v1.metric("Courier ranked #1", f"{ms['kingpin_top1_hits']} / {ms['n_seeds']} seeds")
        v2.metric("Ring recall", f"{ms['recall_mean']:.2f} ± {ms['recall_sd']:.2f}")
        v3.metric("Ring precision", f"{ms['precision_mean']:.2f} ± {ms['precision_sd']:.2f}")
        st.caption(val["caveat"])
    else:
        st.caption(
            "FICN validation not generated on this machine; run "
            "`python -m src.counterfeit.validate` (writes "
            "data/processed/ficn_validation.json)."
        )
