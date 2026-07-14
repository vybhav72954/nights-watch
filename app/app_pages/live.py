"""Beats 1-3 on ONE screen (docs/DEMO_SCRIPT.md).

The old build put the chat on one page and the network on another, which let a
judge watch both halves without ever seeing the seam between them -- and the
seam IS the product. Here the message and the graph share a viewport: you send
the text, the identifiers light up inside the bubble, and the same identifiers
appear as the nodes that pull the report into a known ring. Nothing to narrate.

Everything shown is a `src/` call. `report.gt` is never read (only
`for_model_input()` / public fields), so the answer key can't leak onto stage.
"""
from __future__ import annotations

import core
import streamlit as st
import ui
import whatsapp
from src.detector import detect, entity_spans, guidance
from src.evidence import DEMO_HUB_DEGREE_CAP, build_kingpin_leads
from src.graph import rank_kingpins

CAP = DEMO_HUB_DEGREE_CAP

# Three identifiers in here are load-bearing; keep all three if you ever edit it,
# and re-check BOTH classifier paths afterwards (scam_type stability is a property
# of the wording, not of the code):
#
#   mule00@okaxis   the payee of seeded ring R0000 -- this is the Layer 1 join
#                   (30 reported victims -> 31), and the ONLY thing "Why it
#                   linked" may name.
#   +919999900000   the kingpin's phone. Deliberately the same number the seeded
#                   victims of R0000, R0001 and R0002 were called from, so the
#                   Layer 2 lead is a number the judge just read in the message
#                   rather than one that appears nowhere on screen. Its degree
#                   (54) is far above the hub cap, so Layer 1 refuses to link on
#                   it -- which is exactly the point, and the banner says so.
#   Rs 50,000       the reported loss, so the ring's rupee total moves visibly.
#
# The wording is deliberately free of parcel/courier/customs pretext: with that in
# it, the LLM path called this parcel_customs (0.98) while the rules floor called
# it digital_arrest (0.90) -- both defensible, but the verdict card would change
# label if the venue network dropped mid-demo. It now reads digital_arrest on BOTH
# paths, which is what the pill and the deck promise.
HERO = (
    "URGENT: This is Inspector Sharma, CBI Cyber Crime Branch. Your Aadhaar is "
    "linked to a money laundering case and a non-bailable arrest warrant has "
    "been issued in your name. You are under DIGITAL ARREST. Do not disconnect "
    "the video call, and do not tell anyone, this is a confidential "
    "investigation. To avoid jail custody you must transfer a verification fee "
    "of Rs 50,000 to mule00@okaxis within 2 hours. Call +919999900000 now."
)
DECOY = "Hey, just reached home. I'll pay you back the 500 tomorrow, thanks!"
SUGGESTIONS = {
    "⚖️ A digital-arrest scam (demo)": HERO,
    "✅ A normal message": DECOY,
}

whatsapp.inject_css()
ui.inject_css()

# The product in one strip, lit by where the demo actually is: a verdict lights
# DETECT, a Layer 1 join lights LINK — and a joined ring's evidence pack is a
# deterministic render away in the Command centre, so PROVE lights with it.
_join = st.session_state.last_join
_linked = bool(_join and _join.get("ring_id"))
ui.pipeline(
    detected=bool(st.session_state.chat_messages),
    linked=_linked,
    proved=_linked,
)


def _process(text: str) -> None:
    live = st.session_state.live_reports
    _, _, rings_before = core.current_state(CAP, live)

    with st.spinner("Checking…"):
        report = detect(text, channel="whatsapp")

    live.append(report)
    reports, g, rings_after = core.current_state(CAP, live)
    ring = core.ring_containing(rings_after, report.report_id)

    # Every ring that already existed and is now part of the ring this report
    # sits in. Usually one; more than one means this single report BRIDGED rings
    # we were tracking separately -- which is the strongest thing the product can
    # do, so say it rather than reporting a plain join.
    #
    # `before` is the largest of them, deliberately not "whichever member of the
    # new ring we happen to iterate first": `incident_ids` is a frozenset, so an
    # arbitrary pick is nondeterministic across processes (string hashing is
    # salted) and the "+N" delta on stage would flicker run to run as soon as the
    # merged rings differed in size.
    merged, before = [], 0
    if ring:
        merged = [r for r in rings_before if r.incident_ids & ring.incident_ids]
        before = max((r.size for r in merged), default=0)

    ring_hit = None
    if ring and len(merged) > 1:
        ring_hit = (
            f"⚠ These payees are already known, and they are the same network. "
            f"Your report merges {len(merged)} rings we were tracking separately "
            f"into one of {len(ring.incident_ids)} reported incidents."
        )
    elif ring:
        ring_hit = (
            f"⚠ This payee is already known. Your report links to ring "
            f"{ring.ring_id}: {len(ring.incident_ids)} reported incidents."
        )

    st.session_state.chat_messages += [
        {"role": "out", "text": text, "spans": entity_spans(text)},
        {
            "role": "in",
            "report": report,
            "advice": guidance(report, similar_reports_count=(
                len(ring.incident_ids) - 1 if ring else 0)),
            "ring_hit": ring_hit,
        },
    ]
    st.session_state.last_join = (
        {"ring_id": ring.ring_id, "before": before, "after": len(ring.incident_ids),
         "merged": len(merged), "report_id": report.report_id}
        if ring else {"ring_id": None, "report_id": report.report_id}
    )
    st.rerun()


left, right = st.columns([5, 7], gap="medium")

# ---------------------------------------------------------------- the phone
with left:
    st.subheader("Citizen check", anchor=False)
    st.caption("Consent-first: nothing is tapped or tracked. The citizen forwards, we answer.")

    bubbles = [
        whatsapp.forwarded_bubble(m["text"], m["spans"]) if m["role"] == "out"
        else whatsapp.verdict_bubble(m["report"], m["advice"], m["ring_hit"])
        for m in st.session_state.chat_messages
    ]
    st.html(whatsapp.phone(bubbles, contact="Night's Watch",
                           status="online · report a scam"))
    if bubbles:
        st.html(whatsapp.legend())

    if not st.session_state.chat_messages:
        picked = st.pills("Try one", list(SUGGESTIONS), label_visibility="collapsed")
        if picked:
            _process(SUGGESTIONS[picked])

    typed = st.chat_input("Forward a suspicious message…")
    if typed:
        _process(typed)

# ------------------------------------------------------------- the network
with right:
    st.subheader("Live fraud network", anchor=False)

    live = st.session_state.live_reports
    reports, g, rings = core.current_state(CAP, live)
    reports_by_id = {r.report_id: r for r in reports}
    join = st.session_state.last_join

    ring = None
    if join and join.get("ring_id"):
        ring = next((r for r in rings if r.ring_id == join["ring_id"]), None)

    if ring:
        stats = core.ring_stats(ring, reports_by_id)
        linkers = core.linking_identifiers(g, ring, join["report_id"])
        if join.get("merged", 1) > 1:
            st.error(
                f"**One report merged {join['merged']} known rings.** The identifiers in "
                f"that message are shared with more than one ring we were tracking "
                f"separately. They are one network.",
                icon=":material/warning:",
            )
        else:
            st.error(
                f"**Linked to known ring {ring.ring_id}.** The payee in that message "
                f"is already in our intelligence base.",
                icon=":material/warning:",
            )
        m = st.columns(3)
        m[0].metric("Incidents in this ring", stats["incidents"],
                    delta=f"+{stats['incidents'] - join['before']}"
                    if join["before"] else None)
        m[1].metric("Reported loss in this ring", core.rupees(stats["reported_loss"]),
                    delta=f"{stats['victims_with_loss']} victims")
        m[2].metric("Shared hard identifiers", len(linkers))
        if linkers:
            chips = " ".join(
                f":blue-badge[{n.split(':', 1)[1]}]" for n in linkers)
            st.markdown(f"**Why it linked (Layer 1, deterministic):** {chips}")
    else:
        m = st.columns(3)
        m[0].metric("Rings in the intelligence base", len(rings))
        m[1].metric("Reports in the graph",
                    sum(1 for _, d in g.nodes(data=True) if d["kind"] == "incident"))
        m[2].metric("Live this session", len(live))
        if join:
            st.info("No prior report shares an identifier with this message, so there is "
                    "nothing to link. One report is not a ring.", icon=":material/info:")

    scores = rank_kingpins(g, rings)
    top = scores[0].node if scores else None
    focus = f"incident:{join['report_id']}" if join else None
    # 360px, not more: the camera fits the joined ring to the frame whatever the
    # height, and the kingpin banner below must stay above a 1000px fold with
    # the pipeline strip now above (§16.6 — measured, not guessed).
    html, undrawn = core.graph_html(
        CAP, tuple(r.report_id for r in live), top, live,
        focus_node=focus, height=360, show_hubs=False,
    )
    st.iframe(html, height=380)

    # The kingpin lead goes directly under the graph and ABOVE the caption: it is
    # the payoff of this whole screen, and at 520px of graph plus a three-line
    # caption it rendered below the fold on a 1050px viewport -- present in the
    # DOM, invisible in the room. The caption is small print and can sit under it.
    if ring and scores:
        leads = build_kingpin_leads(scores, rings, top_k=1)
        lead = leads[0] if leads else None
        if lead and len(lead.bridged_ring_ids) > 1:
            # Only claim the lead is *in the message* when it actually is -- for the
            # hero it is (its phone is the kingpin's), but a judge's own text may
            # join a ring the kingpin never touches, and over-claiming there would
            # be the same false-link mistake the guardrails exist to prevent.
            named_here = g.has_edge(f"incident:{join['report_id']}", lead.node)
            st.warning(
                (f"**The number that called you is the thread.** `{lead.node}` "
                 if named_here else
                 f"**And it doesn't stop at this ring.** `{lead.node}` ")
                + f"is central across **{len(lead.bridged_ring_ids)} rings** "
                f"({', '.join(sorted(lead.bridged_ring_ids))}): different scams, one "
                f"controller. Too many incidents touch it for Layer 1 to link on it "
                f"(popular ≠ fraud, the same guardrail that protects a busy merchant), "
                f"so it is a Layer 2 **lead, not proof**.",
                icon=":material/hub:",
            )

    # No red-star clause: the kingpin's degree (54) is above the cap, so it IS one
    # of the capped hubs and is not drawn on this page either.
    st.caption(
        f"Ring identifiers are filled by ring and outlined by identifier type, the same "
        f"colours as the highlights in the message. Green = your live report. "
        f"{undrawn:,} legit background reports not drawn. The capped hubs (popular ≠ "
        f"fraud) and the Layer 2 kingpin lead are drawn in the Command centre."
    )
    st.page_link("app_pages/command_centre.py", label="Open the Command centre",
                 icon=":material/hub:")

    # Collapsed by default so it costs no fold space; the mechanics for the
    # judge who asks. Qualitative on purpose — the measured numbers live in the
    # Validation tab, read from the code-produced artifacts.
    if ring:
        with st.expander("What just happened, exactly?"):
            st.markdown(
                "- **Detect**: the classifier read the raw text and returned a "
                "verdict with the red flags it fired on; extraction pulled the "
                "identifiers highlighted in the bubble. The citizen gets guidance; "
                "the graph gets a structured report. Consent-first: nothing was "
                "tapped; the citizen pasted it.\n"
                "- **Link**: every hard identifier (payee UPI, phone, account, "
                "device) is a node; two reports naming the same one share an edge. "
                "This report named a payee already in the intelligence base, so it "
                "joined that ring **deterministically**; nothing learned, nothing "
                "inferred. That is Layer 1, the court-facing claim.\n"
                "- **Prove**: the ring's evidence pack (every shared identifier, "
                "every incident, hash-stamped) is one click away in the Command "
                "centre. The kingpin banner is Layer 2, a prioritisation lead, "
                "never cited as proof."
            )
