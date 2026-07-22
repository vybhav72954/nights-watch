"""FICN (counterfeit-currency) demo glue -- the Link/Prove spine re-pointed to
seizure records, rendered for the app. Mirrors `core.py`'s scam helpers for the
counterfeit world.

Wiring only: every computation is a `src.counterfeit` or `src` call, and nothing
here reads a seizure's ground truth (`gt`) -- the same discipline as `core.py`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "app")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
from pyvis.network import Network

from core import BG, EDGE_COLOR, FG, HUB_COLOR, INCIDENT_COLOR, KINGPIN_COLOR, RING_PALETTE
from src.counterfeit.generate import FICN_HUB_DEGREE_CAP, SeizureRecord, generate_seizures
from src.counterfeit.graph import build_seizure_graph
from src.graph import Ring, detect_rings, hub_nodes, rank_kingpins  # noqa: F401 (rank_kingpins re-exported)

# The hub-cap ladder for the FICN slider -- same story as the scam curve: below
# the courier bridge (degree 29) the rings stay separate and clean; at/above it
# the one courier account fuses its two rings and precision falls. 24 is the demo
# cap, sitting above every ring's own serial (<=18) and below the bridge.
FICN_CAPS = [12, 18, 24, 29, 40, None]

# Identifier-kind colours: serial = the reused printing plate (the ring link);
# account = the courier laundering proceeds (the cross-ring bridge).
SERIAL_COLOR = "#38bdf8"
ACCOUNT_COLOR = "#a78bfa"
_KIND_COLOR = {"serial": SERIAL_COLOR, "account": ACCOUNT_COLOR}


@st.cache_resource(show_spinner="Seeding the counterfeit-circulation base…")
def seeded_seizures() -> list[SeizureRecord]:
    """The seeded FICN intelligence base (seed 0): five reused-plate rings of
    18/11/7/5/4 seizures, the first two bridged by one courier account, over a
    background of isolated one-off genuine-note recoveries."""
    return generate_seizures(seed=0)


def seizure_state(cap: int | None = FICN_HUB_DEGREE_CAP):
    """Rebuilt per call (the graph is small). Returns (seizures, graph, rings)."""
    seizures = seeded_seizures()
    g = build_seizure_graph(seizures)
    rings = detect_rings(g, hub_degree_cap=cap)
    return seizures, g, rings


def ring_face_value(ring: Ring, by_id: dict[str, SeizureRecord]) -> int:
    """Total counterfeit face value in a ring -- the FICN analogue of the scam
    ring's reported-loss total."""
    return sum(
        by_id[n.split(":", 1)[1]].face_value
        for n in ring.incident_ids
        if n.split(":", 1)[1] in by_id
    )


@st.cache_data(show_spinner="Rendering the circulation network…", max_entries=16)
def seizure_graph_html(
    cap: int | None = FICN_HUB_DEGREE_CAP,
    kingpin_node: str | None = None,
    height: int = 560,
    show_hubs: bool = True,
) -> tuple[str, int]:
    """Self-contained pyvis document for the FICN graph (vis.js inlined, offline
    safe) -- the same recipe as `core.graph_html`, minus the live-report
    machinery. Serial nodes are triangles (the reused plate), account nodes are
    dots (the courier); a capped hub is a diamond, the kingpin courier a red
    star. Returns (html, n_incidents_not_drawn)."""
    _, g, rings = seizure_state(cap)
    hubs = hub_nodes(g, cap) if cap is not None else set()
    working = g.copy()
    working.remove_nodes_from(hubs)

    ring_of: dict[str, int] = {}
    for i, ring in enumerate(rings):
        for n in ring.incident_ids | ring.identifier_nodes:
            ring_of[n] = i
    shown = set(ring_of)

    net = Network(height=f"{height}px", width="100%", bgcolor=BG, font_color=FG,
                  notebook=False, cdn_resources="in_line")

    def _kingpin(n: str) -> bool:
        return kingpin_node is not None and n == kingpin_node

    for n in sorted(shown):
        kind = g.nodes[n]["kind"]
        idx = ring_of.get(n)
        in_ring = f" · ring {rings[idx].ring_id}" if idx is not None else ""
        if kind == "incident":
            net.add_node(
                n, label=" ", shape="dot", size=8, color=INCIDENT_COLOR, borderWidth=1,
                title=f"seizure · {g.nodes[n].get('scam_type', '?')}{in_ring}",
            )
        else:
            fill = RING_PALETTE[idx % len(RING_PALETTE)] if idx is not None else INCIDENT_COLOR
            border = _KIND_COLOR.get(kind, fill)
            net.add_node(
                n,
                label=n.split(":", 1)[1],
                shape="star" if _kingpin(n) else ("triangle" if kind == "serial" else "dot"),
                size=26 if _kingpin(n) else 15,
                borderWidth=3,
                color=(KINGPIN_COLOR if _kingpin(n)
                       else {"background": fill, "border": border,
                             "highlight": {"background": fill, "border": "#ffffff"}}),
                title=f"{kind} · degree {g.degree(n)}{in_ring}"
                      + (" · LAYER-2 KINGPIN LEAD (not proof)" if _kingpin(n) else ""),
            )

    for u, v in working.subgraph(shown).edges():
        net.add_edge(u, v, color=EDGE_COLOR)

    # capped hubs: drawn WITHOUT edges -- present, but not allowed to glue rings
    # together (the guardrail, visualised). The courier account lands here.
    for n in sorted(hubs if show_hubs else ()):
        net.add_node(
            n, label=n.split(":", 1)[1],
            shape="star" if _kingpin(n) else "diamond",
            size=28 if _kingpin(n) else 18,
            color=KINGPIN_COLOR if _kingpin(n) else HUB_COLOR,
            title=f"{g.nodes[n]['kind']} · degree {g.degree(n)} · excluded by cap (fan-in ≠ proof)"
                  + (" · LAYER-2 KINGPIN LEAD (not proof)" if _kingpin(n) else ""),
        )

    net.set_options(json.dumps({
        "layout": {"randomSeed": 7},
        "physics": {"stabilization": {"enabled": True, "iterations": 200},
                    "barnesHut": {"gravitationalConstant": -6000, "springLength": 110}},
        "interaction": {"hover": True, "tooltipDelay": 120},
        "nodes": {"font": {"color": FG, "size": 13}},
        "edges": {"smooth": False},
    }))

    html = net.generate_html().replace("border: 1px solid lightgray;", "border: none;")
    html = html.replace(
        "</head>",
        f"<style>html,body{{margin:0;padding:0;background:{BG};}}"
        f".card{{background:{BG} !important;border:none !important;}}</style></head>",
    )
    html = html.replace(
        "</body>",
        "<script>network.once('stabilizationIterationsDone',function(){"
        "network.setOptions({physics:false});});</script></body>",
    )
    total = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "incident")
    shown_inc = sum(1 for n in shown if g.nodes[n]["kind"] == "incident")
    return html, total - shown_inc
