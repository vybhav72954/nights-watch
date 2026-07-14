"""Beats 2-5 -- the command centre: live network, kingpin leads, evidence
packs, and the validation story (curve + guardrails + lead time)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import core
import ui
from src.evidence import (
    DEFAULT_CURVE_CAPS,
    DEMO_HUB_DEGREE_CAP,
    adversarial_split_reports,
    build_evidence_pack,
    build_kingpin_leads,
    describe_adversarial_case,
    lead_time_headline,
    legit_hub_guardrail,
    precision_recall_curve,
)
from src.graph import build_graph, rank_kingpins

st.title("Command centre")
ui.inject_css()
# The two-layer doctrine is §3's differentiator; it belongs above the tabs as a
# fixture of this screen, not buried in one tab's caption.
ui.layer_cards()


def _cap_label(c: int | None) -> str:
    return "uncapped" if c is None else str(c)


cap = st.select_slider(
    "Hub degree cap: the live precision/recall threshold. Layer 1 ignores any "
    "identifier touched by more incidents than this (popular ≠ fraud).",
    options=DEFAULT_CURVE_CAPS,
    value=DEMO_HUB_DEGREE_CAP,
    format_func=_cap_label,
)

live = st.session_state.live_reports
reports, g, rings = core.current_state(cap, live)
reports_by_id = {r.report_id: r for r in reports}
scores = rank_kingpins(g, rings) if rings else []
leads = build_kingpin_leads(scores, rings, top_k=5) if scores else []
top_node = leads[0].node if leads else None

tab_net, tab_king, tab_ev, tab_val = st.tabs(
    [":material/hub: Network", ":material/star: Kingpins",
     ":material/description: Evidence", ":material/verified: Validation"]
)

with tab_net:
    last_join = st.session_state.last_join
    joined_ring = last_join.get("ring_id") if last_join else None
    # Claim growth only when the live report actually joined a ring, at the cap
    # that join was measured at, and the ring it joined is the one on show here.
    # A report that linked to nothing carries no before/after at all, so this
    # guard is also what stops the decoy (and any judge-typed message that
    # happens not to link) from crashing this page with a KeyError.
    shows_join = (
        joined_ring is not None
        and cap == DEMO_HUB_DEGREE_CAP
        and rings
        and rings[0].ring_id == joined_ring
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rings detected", len(rings))
    c2.metric(
        "Largest ring",
        rings[0].size if rings else 0,
        delta=(last_join["after"] - last_join["before"]) if shows_join else None,
    )
    c3.metric("Reports in graph", len(reports))
    c4.metric("Live this session", len(live))

    live_key = tuple(r.report_id for r in live)
    html, n_hidden = core.graph_html(cap, live_key, top_node, live)
    st.iframe(html, height=660)
    st.caption(
        "⬤ grey = incident · ⬤ colour = ring identifiers (one colour per ring) · "
        "⬤ green = live report · ◆ orange = high-degree hub, excluded by the cap · "
        "★ red = Layer-2 kingpin lead. "
        f"{n_hidden} background incidents not drawn (no ring membership)."
    )

with tab_king:
    st.subheader("Layer 2: prioritisation leads · not proof")
    if not leads:
        st.info("No rings at this cap, so no kingpin leads to rank.")
    for i, lead in enumerate(leads, start=1):
        with st.container(border=True):
            st.markdown(f"**#{i} · `{lead.node}`** · centrality score {lead.score:.3f}")
            st.markdown(
                f"Bridges **{len(lead.bridged_ring_ids)}** ring(s) "
                f"({', '.join(lead.bridged_ring_ids)}) · "
                f"{lead.bridged_incident_count} linked incidents"
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
        # The methodology stamp comes off the ring (it records the cap this ring
        # was actually detected at), so moving the slider can't desync the pack
        # from how its ring was found.
        pack = build_evidence_pack(ring, g, reports_by_id)

        st.markdown(f"Pack integrity hash (SHA-256): `{pack.content_sha256}`")
        pdf_path = (Path(tempfile.gettempdir())
                    / f"nightswatch_{ring_id}_{pack.content_sha256[:8]}.pdf")
        if not pdf_path.exists():
            pack.to_pdf(pdf_path)
        d1, d2 = st.columns(2)
        d1.download_button(
            ":material/download: Evidence pack (JSON)",
            data=json.dumps(pack.to_dict(), indent=2, default=str),
            file_name=f"evidence_{ring_id}.json",
            mime="application/json",
        )
        d2.download_button(
            ":material/download: Evidence pack (PDF)",
            data=pdf_path.read_bytes(),
            file_name=f"evidence_{ring_id}.pdf",
            mime="application/pdf",
        )
        st.markdown(pack.to_markdown())

with tab_val:
    st.subheader("Does it actually work? The answer-key numbers")
    st.caption(
        "Everything below is computed on the seeded corpus only; live reports "
        "join the graph, never the metric (they carry no ground truth)."
    )

    @st.cache_data(show_spinner="Running answer-key validation…")
    def _validation_artifacts():
        seeded = core.seeded_reports()
        g0 = build_graph(seeded)
        curve = precision_recall_curve(seeded, g0, DEFAULT_CURVE_CAPS)
        hub_ok = legit_hub_guardrail(
            g0, core.find_legit_hub(g0), hub_degree_cap=DEMO_HUB_DEGREE_CAP,
        )
        # The rotator scenario only has tension while the shared device's degree
        # EXCEEDS the cap -- that is the whole point (the guardrail that protects
        # Swiggy also hides this device from Layer 1). Its default victim count
        # tracks DEMO_HUB_DEGREE_CAP; see `adversarial_split_reports`.
        adv_ok = describe_adversarial_case(
            adversarial_split_reports(seed=0), hub_degree_cap=DEMO_HUB_DEGREE_CAP,
        )
        # Lead time runs on the seeded corpus itself, not a network conjured for
        # the purpose -- same rings, same cap, same numbers as every other page.
        replays = core.lead_time_replays()
        return curve, hub_ok, adv_ok, lead_time_headline(replays), replays

    curve, hub_ok, adv_ok, headline, replays = _validation_artifacts()

    order = [_cap_label(c) for c in DEFAULT_CURVE_CAPS]
    df = pd.DataFrame(
        [
            {"cap": _cap_label(s.hub_degree_cap), "metric": m, "value": getattr(s, m)}
            for s in curve
            for m in ("precision", "recall", "f1")
        ]
    )
    # Explicit colours and dashes: Streamlit's default Altair palette gave
    # precision and f1 two near-identical blues, and the three metrics sit
    # exactly on top of each other across caps 4-10 (all 1.0) -- so the one
    # chart whose job is to prove precision AND recall are 1.0 there was
    # drawing a single indistinguishable line. The y-axis had no value labels
    # at all, which left the 1.0 unreadable even when you could tell the lines
    # apart.
    metric_color = alt.Color(
        "metric:N",
        legend=alt.Legend(orient="top", title=None),
        scale=alt.Scale(domain=["precision", "recall", "f1"],
                        range=["#38bdf8", "#f472b6", "#fbbf24"]),
    )
    lines = (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=2.5, opacity=0.9)
        .encode(
            x=alt.X("cap:N", sort=order, title="hub degree cap"),
            y=alt.Y(
                "value:Q", title=None,
                scale=alt.Scale(domain=[0, 1.05]),
                axis=alt.Axis(values=[0, 0.25, 0.5, 0.75, 1.0], format=".0%"),
            ),
            color=metric_color,
            strokeDash=alt.StrokeDash(
                "metric:N",
                scale=alt.Scale(domain=["precision", "recall", "f1"],
                                range=[[1, 0], [6, 3], [2, 2]]),
                legend=alt.Legend(orient="top", title=None),
            ),
        )
    )
    rule = (
        alt.Chart(pd.DataFrame({"cap": [_cap_label(cap)]}))
        .mark_rule(strokeDash=[4, 4], color="#e6edf3")
        .encode(x=alt.X("cap:N", sort=order))
    )
    st.altair_chart(lines + rule)
    st.caption(
        "Ring-recovery precision/recall vs the cap (dashed line = the live slider). "
        "Caps 5–20: too strict, because the cap excludes the bigger rings' own mule UPIs, so "
        "those rings are never recovered at all and recall collapses (precision stays "
        "1.0 only because the little that is still claimed is correct). 30–50: every "
        "ring recovered, nothing false. 60 re-admits the kingpin's bridging phone "
        "(degree 53) and fuses its three rings into one. 80 re-admits the common "
        "merchants. Uncapped, the legit hub fuses nearly everything. Both failure ends "
        "are left visible on purpose; that's what shows the 1.0s in the middle "
        "aren't rigged."
    )

    st.divider()
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.markdown("**Guardrail: legit high-degree hub**")
        (st.success if hub_ok.passed else st.error)(hub_ok.detail)
    with gcol2:
        st.markdown("**Guardrail: adversarial identifier rotation**")
        (st.success if adv_ok.passed else st.error)(adv_ok.detail)

    # ── the slide-8 numbers, in the app ──────────────────────────────────────
    # Read from the code-produced artifacts in data/processed/, never typed in:
    # a number hard-coded here would be an asserted one (§17), and data/ is
    # gitignored, so on a machine that hasn't generated an artifact the page
    # shows the command that produces it instead of a stale figure.
    st.divider()
    st.markdown("**Measured on real data: the false-positive numbers**")
    uci = core.processed_artifact("uci_eval")
    nus = core.processed_artifact("nus_eval")
    val = core.processed_artifact("validation")

    r1, r2, r3 = st.columns(3)
    with r1:
        if uci:
            # no delta=: st.metric stamps an arrow on it, and an "↑" next to an
            # FP rate reads as "rising" -- the rate lives in the caption instead
            st.metric(
                "Real ham flagged (UCI)",
                f"{uci['ham_false_positives']} / {uci['n_ham']:,}",
            )
            st.caption(
                f"A {uci['ham_false_positive_rate']:.2%} false-positive rate on the "
                "UCI SMS Spam Collection (real human SMS, rules floor). Caveat, "
                "stated out loud: this eval *found* two keyword-bug classes and "
                "now guards their fixes, so it is a regression harness, not an "
                "untouched held-out set. That is what the NUS number is for."
            )
        else:
            st.caption(
                "UCI eval not generated on this machine; run "
                "`python -m src.detector.eval_uci` (needs the gitignored corpus, "
                "docs/DATASETS.md §2)."
            )
    with r2:
        if nus:
            st.metric(
                "Real SMS flagged (NUS, held out)",
                f"{nus['false_positives']} / {nus['n_messages']:,}",
            )
            st.caption(
                f"A {nus['false_positive_rate']:.2%} false-positive rate on the "
                "NUS SMS Corpus: 55k+ real conversational SMS the keyword lists "
                "have never seen in either direction. No code was changed in "
                "response to this number; it is frozen as measured."
            )
        else:
            st.caption(
                "NUS eval not generated on this machine; run "
                "`python -m src.detector.eval_nus` (downloads the corpus, "
                "docs/DATASETS.md §2)."
            )
    with r3:
        if val:
            ms = val["multi_seed"]
            st.metric(
                "Kingpin ranked #1",
                f"{ms['kingpin_top1_hits']} / {ms['n_seeds']} seeds",
            )
            st.caption(
                f"Ring recovery precision "
                f"{ms['precision_mean']:.2f}±{ms['precision_sd']:.2f}, recall "
                f"{ms['recall_mean']:.2f}±{ms['recall_sd']:.2f} across "
                f"{ms['n_seeds']} independently seeded networks at cap "
                f"{ms['hub_degree_cap']}, scored against the planted answer key. "
                "Planted rings are clean by design; the claim is that the method "
                "recovers the answer key exactly, not that real-world data is "
                "this clean."
            )
        else:
            st.caption(
                "Answer-key validation not generated on this machine; run "
                "`python -m src.evidence.validate`."
            )

    scale = core.processed_artifact("scale_benchmark")
    with st.expander("Does it scale? Pipeline latency vs network size"):
        if scale:
            runs = scale["runs"]
            sdf = pd.DataFrame(
                [
                    {
                        "reports": r["n_reports"],
                        "seconds": (r["build_graph_seconds"]
                                    + r["detect_rings_seconds"]
                                    + r["rank_kingpins_seconds"]),
                        "rings detected": r["n_rings_detected"],
                    }
                    for r in runs
                ]
            )
            st.altair_chart(
                alt.Chart(sdf)
                .mark_line(point=True, strokeWidth=2.5, color="#38bdf8")
                .encode(
                    x=alt.X("reports:Q", title="reports in the graph",
                            axis=alt.Axis(format="~s")),
                    y=alt.Y("seconds:Q", title="seconds"),
                    tooltip=["reports", alt.Tooltip("seconds", format=".2f"),
                             "rings detected"],
                )
            )
            big = sdf.iloc[-1]
            st.caption(
                f"Graph build + ring detection + kingpin ranking, end to end: "
                f"{int(big['reports']):,} reports in {big['seconds']:.1f}s on a "
                f"laptop CPU (`python -m src.evidence.scale_benchmark`; "
                f"synthetic-corpus *generation* time excluded; that is data "
                f"creation, not the pipeline)."
            )
        else:
            st.caption(
                "Scale benchmark not generated on this machine; run "
                "`python -m src.evidence.scale_benchmark`."
            )

    st.divider()
    if headline:
        st.info(f"**Lead time:** {headline}")
    st.page_link("app_pages/replay.py", label="Replay it report by report",
                 icon=":material/schedule:")
