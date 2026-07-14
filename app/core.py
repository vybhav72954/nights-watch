"""Glue for the Streamlit demo: cached seeded state, per-rerun graph assembly,
and the pyvis network view. Wiring only -- every computation is a src/ call
(docs/APP_DESIGN.md ADR-3), and nothing here may read report.gt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "app")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import networkx as nx
import streamlit as st
from pyvis.network import Network

from src.evidence import DEMO_HUB_DEGREE_CAP, LeadTimeReplay, replay_lead_time
from src.generate import generate_network
from src.graph import Ring, build_graph, detect_rings, hub_nodes
from src.schema import Report
from whatsapp import IDENT_COLORS

BG = "#0e1420"
FG = "#e6edf3"
EDGE_COLOR = "#31405c"
INCIDENT_COLOR = "#5b6779"
LIVE_COLOR = "#22c55e"
HUB_COLOR = "#f97316"
KINGPIN_COLOR = "#ef4444"
RING_PALETTE = [
    "#38bdf8", "#a78bfa", "#f472b6", "#fbbf24", "#2dd4bf", "#818cf8",
    "#e879f9", "#fb7185", "#a3e635", "#67e8f9",
]


@st.cache_resource(show_spinner="Seeding the intelligence graph (seed=0)…")
def seeded_reports() -> list[Report]:
    """The pre-seeded intelligence base: 6 planted rings of 30/14/9/6/5/4
    victims (a kingpin phone bridges the first 3, which run three *different*
    pretexts) over a 500-victim legit background with one high-degree legit hub
    UPI. One world -- the citizen's report joins ring R0000 here, and the
    lead-time replay below runs on this same corpus."""
    return generate_network(seed=0)


@st.cache_resource(show_spinner="Replaying the intelligence base…")
def lead_time_replays() -> list[LeadTimeReplay]:
    """G1's counterfactual, computed once per process on the SEEDED corpus --
    the same rings the rest of the app draws (B7: live reports join the graph,
    never a metric).

    Shared by the replay page and the command centre so there is exactly one
    lead-time number in the app. It used to be two: the pages each generated a
    throwaway one-ring network of 30 victims, because the old cap (10) made a
    ring bigger than 10 undetectable, so the seeded world *couldn't* host the
    ring the closer needed. A judge therefore saw a ring of 5 on the hero
    screen and a ring of 30 on the closer. It is O(n^2) -- ~2.5s here, fine at
    seeded-corpus scale, and cached."""
    return replay_lead_time(
        seeded_reports(), hub_degree_cap=DEMO_HUB_DEGREE_CAP, min_incidents=2,
    )


def current_state(
    cap: int | None, live: list[Report],
) -> tuple[list[Report], nx.Graph, list[Ring]]:
    """Rebuilt every rerun -- correct-by-reconstruction beats cache
    invalidation at ~320 reports (ADR-3)."""
    reports = seeded_reports() + list(live)
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=cap)
    return reports, g, rings


def ring_containing(rings: list[Ring], report_id: str) -> Ring | None:
    node = f"incident:{report_id}"
    return next((r for r in rings if node in r.incident_ids), None)


def find_legit_hub(g: nx.Graph) -> str:
    """Highest-degree UPI node in the seeded graph -- the planted legit hub."""
    return max((n for n, d in g.nodes(data=True) if d["kind"] == "upi"), key=g.degree)


def linking_identifiers(g: nx.Graph, ring: Ring, report_id: str) -> list[str]:
    """The identifier nodes that actually joined this report to the ring -- the
    answer to "why did it link?", and the whole Layer 1 claim: a shared hard
    identifier, nothing learned, nothing inferred.

    Both conditions are load-bearing, and this is the same rule the evidence
    pack applies (`pack.build_evidence_pack`), so the screen and the court
    document can never disagree:

    * `ident in ring.identifier_nodes` -- rings are computed hub-pruned, so this
      excludes the capped hubs. Without it, a message that named the popular
      merchant alongside the mule put `swiggy@ybl` on screen under "Why it
      linked (Layer 1, deterministic)" -- crediting the legit hub with a link
      Layer 1 had explicitly refused to draw, which is the exact false positive
      the whole guardrail exists to prevent.
    * another incident *of this ring* must name it -- an identifier only this
      report carries (its own phone) forms no edge and links nobody.
    """
    node = f"incident:{report_id}"
    if node not in g:
        return []
    return sorted(
        ident
        for ident in g.neighbors(node)
        if ident in ring.identifier_nodes
        and any(nb != node and nb in ring.incident_ids for nb in g.neighbors(ident))
    )


def ring_stats(ring: Ring, reports_by_id: dict[str, Report]) -> dict:
    """Ring economics. `amount` is extracted on every report and was going
    unused -- summing it turns "a component of 5 nodes" into "Rs 2.4 lakh of
    reported loss", which is the unit a public-safety judge actually thinks in."""
    incidents = [
        reports_by_id[n.split(":", 1)[1]]
        for n in ring.incident_ids
        if n.split(":", 1)[1] in reports_by_id
    ]
    losses = [r.entities.amount for r in incidents if r.entities.amount]
    types = {r.verdict.scam_type for r in incidents if r.verdict.scam_type != "legit"}
    return {
        "incidents": len(incidents),
        "reported_loss": sum(losses),
        "victims_with_loss": len(losses),
        "scam_types": sorted(types),
        "identifiers": len(ring.identifier_nodes),
    }


def rupees(amount: int) -> str:
    """Indian-convention short form -- a judge reads 'Rs 2.4L' faster than 240000."""
    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.2f} Cr"
    if amount >= 100_000:
        return f"₹{amount / 100_000:.2f} L"
    return f"₹{amount:,}"


def processed_artifact(name: str) -> dict | None:
    """A code-produced artifact from data/processed/ (uci_eval, nus_eval,
    validation, scale_benchmark), or None if it hasn't been generated on this
    machine -- data/ is gitignored, so a fresh clone has none of them.

    The app reads these instead of hard-coding the numbers: §17's rule is that
    every quantitative claim is produced by code in this repo, and a number
    typed into the UI would be an asserted one. When the artifact is absent the
    page shows the regeneration command, never a stale figure.
    """
    path = _REPO_ROOT / "data" / "processed" / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# graph node "kind" -> the identifier colour used in the WhatsApp bubble, so a
# highlighted identifier and its node read as the same thing (whatsapp.py).
# Keys are the node kinds `build_graph` actually emits: upi, phone, account
# (an IFSC resolves to the same account node), device. `device` is absent on
# purpose -- it has no bubble highlight to match (it comes from the LLM, not a
# span), so it takes the ring fill like any other node.
_KIND_TO_IDENT = {"upi": "payee_upi", "phone": "phone", "account": "account"}


@st.cache_data(show_spinner="Rendering the network…", max_entries=32)
def graph_html(
    cap: int | None,
    live_key: tuple[str, ...],
    kingpin_node: str | None,
    _live: list[Report],
    focus_node: str | None = None,
    height: int = 640,
    show_hubs: bool = True,
) -> tuple[str, int]:
    """Self-contained pyvis document (vis.js inlined -- offline-safe, ADR-2).

    Cached on (cap, live_key, kingpin_node, focus_node, height, show_hubs) so
    unrelated reruns reuse the byte-identical document and the iframe never
    re-mounts or re-runs physics (APP_DESIGN §6.1). Returns
    (html, n_incidents_not_drawn) -- the legit background stays undrawn,
    reported as a count instead.

    Identifier nodes are filled by ring and outlined by identifier kind: the
    fill answers "which ring", the outline answers "which highlighted thing in
    the message this is".

    `show_hubs=False` omits the capped hub nodes. They carry no edges, so when
    the camera fits a single ring (the Live page) a hub parked outside that
    frame renders as a half-cut orange diamond against the panel edge, which
    reads as a broken widget. The hubs -- and the popular-is-not-fraud story
    they carry -- belong to the Command centre, where the camera fits the whole
    network and nothing can clip.
    """
    _, g, rings = current_state(cap, _live)

    hubs = hub_nodes(g, cap) if cap is not None else set()
    working = g.copy()
    working.remove_nodes_from(hubs)

    ring_of: dict[str, int] = {}
    for i, ring in enumerate(rings):
        for n in ring.incident_ids | ring.identifier_nodes:
            ring_of[n] = i

    live_incidents = {f"incident:{rid}" for rid in live_key}
    shown: set[str] = set(ring_of)
    for inc in live_incidents:  # a live report outside any ring still shows
        if inc in working:
            shown.add(inc)
            shown.update(working.neighbors(inc))

    net = Network(height=f"{height}px", width="100%", bgcolor=BG, font_color=FG,
                  notebook=False, cdn_resources="in_line")

    def _kingpin(n: str) -> bool:
        return kingpin_node is not None and n == kingpin_node

    for n in sorted(shown):
        kind = g.nodes[n]["kind"]
        ring_idx = ring_of.get(n)
        in_ring = f" · ring {rings[ring_idx].ring_id}" if ring_idx is not None else ""
        if kind == "incident":
            live = n in live_incidents
            net.add_node(
                n,
                label="YOUR REPORT" if live else " ",
                shape="dot",
                size=18 if live else 7,
                color=LIVE_COLOR if live else INCIDENT_COLOR,
                borderWidth=3 if live else 1,
                shadow={"enabled": True, "color": LIVE_COLOR, "size": 26} if live else False,
                title=f"incident · {g.nodes[n].get('scam_type', '?')}{in_ring}",
            )
        else:
            fill = (RING_PALETTE[ring_idx % len(RING_PALETTE)]
                    if ring_idx is not None else INCIDENT_COLOR)
            border = IDENT_COLORS.get(_KIND_TO_IDENT.get(kind, ""), fill)
            net.add_node(
                n,
                label=n.split(":", 1)[1],
                shape="star" if _kingpin(n) else "dot",
                size=26 if _kingpin(n) else 12,
                borderWidth=3,
                color=(KINGPIN_COLOR if _kingpin(n)
                       else {"background": fill, "border": border,
                             "highlight": {"background": fill, "border": "#ffffff"}}),
                title=f"{kind} · degree {g.degree(n)}{in_ring}"
                      + (" · LAYER-2 KINGPIN LEAD (not proof)" if _kingpin(n) else ""),
            )

    for u, v in working.subgraph(shown).edges():
        net.add_edge(u, v, color=EDGE_COLOR)

    # hub-capped identifiers: drawn WITHOUT their edges -- present, but not
    # allowed to glue rings together (the guardrail, visualised)
    for n in sorted(hubs if show_hubs else ()):
        net.add_node(
            n,
            label=n.split(":", 1)[1],
            shape="star" if _kingpin(n) else "diamond",
            size=26 if _kingpin(n) else 18,
            color=KINGPIN_COLOR if _kingpin(n) else HUB_COLOR,
            title=f"{g.nodes[n]['kind']} · degree {g.degree(n)}"
                  " · excluded by cap (popular ≠ fraud)"
                  + (" · LAYER-2 KINGPIN LEAD (not proof)" if _kingpin(n) else ""),
        )

    net.set_options(json.dumps({
        "layout": {"randomSeed": 7},
        "physics": {
            "stabilization": {"enabled": True, "iterations": 200},
            "barnesHut": {"gravitationalConstant": -6000, "springLength": 110},
        },
        "interaction": {"hover": True, "tooltipDelay": 120},
        "nodes": {"font": {"color": FG, "size": 13}},
        "edges": {"smooth": False},
    }))

    # pyvis renders a white bootstrap `.card` on a white `<body>` and hard-codes
    # `border: 1px solid lightgray` on the network div. Against the dark theme
    # that framed every graph embed in a pale box. Paint the whole embedded
    # document the app's background instead of patching the pieces.
    html = net.generate_html().replace("border: 1px solid lightgray;", "border: none;")
    html = html.replace(
        "</head>",
        f"<style>html,body{{margin:0;padding:0;background:{BG};}}"
        f".card{{background:{BG} !important;border:none !important;}}</style></head>",
    )
    # Freeze layout once settled so the embed never visibly re-jiggles, then
    # (if asked) fly to the live report -- the camera move IS beat 3: the judge
    # watches the graph go find the message they just sent.
    #
    # fit(nodes=the whole ring), not focus(the one node): focus zooms to a fixed
    # scale about a point, which pushed the ring's other identifiers off the
    # edge of a 520px embed. fit frames the ring it just joined -- which is the
    # thing the judge is meant to look at -- and cannot clip it.
    focus = ""
    if focus_node is not None and focus_node in shown:
        idx = ring_of.get(focus_node)
        # Only fly in when the report actually joined a ring. A report that
        # linked to nothing must keep the wide shot -- zooming to a lone node
        # would fill the panel with empty space and hide the network it failed
        # to join, which is the one thing that beat has to show.
        frame = sorted(n for n in shown if ring_of.get(n) == idx) if idx is not None else []
        fly = (
            f"network.fit({{nodes:{json.dumps(frame)},"
            "animation:{duration:900,easingFunction:'easeInOutQuad'}});"
        ) if len(frame) > 1 else ""
        focus = fly + f"network.selectNodes([{json.dumps(focus_node)}]);"
    html = html.replace(
        "</body>",
        "<script>network.once('stabilizationIterationsDone',function(){"
        f"network.setOptions({{physics:false}});{focus}"
        "});</script></body>",
    )
    total_incidents = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "incident")
    shown_incidents = sum(1 for n in shown if g.nodes[n]["kind"] == "incident")
    return html, total_incidents - shown_incidents
