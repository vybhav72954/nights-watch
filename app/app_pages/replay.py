"""The closer: lead time, as motion (CLAUDE.md §15 G1, §17 slide 10).

`replay_lead_time` already computes the counterfactual -- this page only draws
it. Scrub the reports arriving in the order they actually did; the ring becomes
detectable at report k; every report after k is a person who was still going to
be defrauded. That is the difference between a metric on a slide and a room
going quiet.

The scrub is manual on purpose. Autoplay fights the presenter; a slider lets
you hold on the flag while you say the line.

Never reads `report.gt`: the ring's reports come from the DETECTED Layer 1 ring,
and the flag index comes from `replay_lead_time` (which is validation code and
is entitled to the answer key -- the app is not).
"""
from __future__ import annotations

import core
import streamlit as st
import ui
from src.evidence import DEMO_HUB_DEGREE_CAP, lead_time_headline

ui.inject_css()
st.subheader("Lead time: what the graph buys you", anchor=False)
st.caption(
    "The biggest ring in the intelligence base, replayed in the order its reports "
    "actually arrived. Detection is Layer 1 only: a second report sharing a hard "
    "identifier. Seeded corpus only; no live report enters this metric."
)

PRE, FLAG, AFTER, PENDING = "#5b6779", "#22c55e", "#ef4444", "#1e2836"


@st.cache_resource(show_spinner="Replaying the ring…")
def _replay() -> dict:
    """The ring replayed here is R0000 of the SAME seeded world the rest of the
    app draws — the ring the citizen's report joins on the Live page. It used to
    be a throwaway network generated just for this page (one ring, 30 victims),
    because the old hub cap of 10 made a ring larger than 10 undetectable: its
    own mule UPI would exceed the cap and be pruned as a hub. So the seeded world
    literally could not host a ring big enough to carry this counterfactual, and
    a judge saw a ring of 5 on the hero screen and a ring of 30 here.

    Ring identity comes from the BATCH Layer 1 ring at the demo cap, not from
    arrival order and not from the answer key. Resolving it by "the first Layer 1
    ring to appear in arrival order" is wrong and was a real bug: two ordinary
    background reports naming a popular merchant form a 2-node component long
    before that merchant's degree reaches the cap, so the page picked the legit
    hub and put Swiggy on stage as a fraud ring. The cap is a *steady-state*
    guardrail; the ring's identity is not a race. Because rings are hub-pruned,
    a legit hub cannot be in one at all — so this can no longer name one.
    """
    reports = core.seeded_reports()
    _, g, rings = core.current_state(DEMO_HUB_DEGREE_CAP, [])
    replays = core.lead_time_replays()

    ring = rings[0] if rings else None
    by_id = {r.report_id: r for r in reports}
    members = sorted(
        (by_id[n.split(":", 1)[1]] for n in ring.incident_ids), key=lambda r: r.timestamp,
    ) if ring else []

    # The identifier the most of this ring's incidents name -- with hubs already
    # pruned out of the ring, that is its mule payee, by construction.
    payee = max(
        ring.identifier_nodes,
        key=lambda n: sum(1 for nb in g.neighbors(n) if nb in ring.incident_ids),
        default=None,
    ) if ring else None

    # `lead_time_headline` picks the largest DETECTED ring; the page must scrub
    # the ring that headline is about, or the dots and the sentence disagree.
    detected = [r for r in replays if r.detected_at_report is not None]
    lt = max(detected, key=lambda r: r.eventual_size, default=None)

    return {
        "members": members,
        "ring_id": ring.ring_id if ring else None,
        "payee": payee.split(":", 1)[1] if payee else None,
        "flag_at": lt.detected_at_report if lt else None,
        "headline": lead_time_headline(replays),
    }


R = _replay()
members, flag_at, total = R["members"], R["flag_at"], len(R["members"])

st.session_state.setdefault("replay_t", total)

jump = st.container(horizontal=True)
if jump.button("Jump to detection", icon=":material/flag:"):
    st.session_state.replay_t = flag_at or 1
if jump.button("Run to the end", icon=":material/fast_forward:"):
    st.session_state.replay_t = total
if jump.button("Reset", icon=":material/replay:"):
    st.session_state.replay_t = 1

t = st.slider("Reports received", 1, total, key="replay_t")

arrived = members[:t]
detected = flag_at is not None and t >= flag_at
after_flag = max(0, t - flag_at) if flag_at else 0
loss_after = sum(
    r.entities.amount or 0 for r in members[flag_at:t]
) if flag_at else 0

dots = "".join(
    f'<span style="display:inline-block;width:15px;height:15px;margin:3px;'
    f"border-radius:50%;background:{PENDING if i > t else (FLAG if i == flag_at else (AFTER if flag_at and i > flag_at else PRE))};"
    f'border:1px solid {"#334155" if i > t else "transparent"};'
    f'box-shadow:{"0 0 9px " + FLAG if i == flag_at and detected else "none"}" '
    f'title="report {i}"></span>'
    for i in range(1, total + 1)
)
ui.card(
    f"Ring {R['ring_id']}: its reports, in the order they arrived",
    f'<div style="padding:8px 0 4px">{dots}</div>'
    f'<div style="font-size:12.5px;color:#8696a0;padding-bottom:4px">'
    f'<span style="color:{PRE}">●</span> before detection &nbsp;'
    f'<span style="color:{FLAG}">●</span> ring becomes detectable &nbsp;'
    f'<span style="color:{AFTER}">●</span> victims after the flag (preventable) &nbsp;'
    f'<span style="color:#334155">○</span> not yet reported</div>',
)

c = st.columns(4)
c[0].metric("Reports received", t)
c[1].metric("Ring detected?", "Yes" if detected else "Not yet",
            delta=f"at report {flag_at}" if detected else None,
            delta_color="off")
c[2].metric("Victims after the flag", after_flag)
c[3].metric("Loss after the flag", core.rupees(loss_after))

if detected:
    st.error(
        f"Detectable at report **{flag_at}**: two citizens independently naming the same "
        f"payee (`{R['payee']}`). Everyone after that point is a person the network could "
        f"have warned.",
        icon=":material/warning:",
    )
else:
    st.info(
        "One report is not a ring. Layer 1 needs a second, independent incident sharing a "
        "hard identifier before it will claim anything; that restraint is why the "
        "false-positive rate is what it is.",
        icon=":material/info:",
    )

if R["headline"]:
    st.success(f"**Measured, not asserted:** {R['headline']}", icon=":material/verified:")
    st.caption("The sentence above is produced by `src.evidence.replay_lead_time`, "
               "not typed on a slide.")
