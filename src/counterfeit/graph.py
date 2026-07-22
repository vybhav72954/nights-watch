"""Seizure list -> the incident<->identifier bipartite graph, the FICN analogue
of `src.graph.build_graph`.

Structurally identical to the scam graph: seizure-incident nodes (`kind =
"incident"`, so `detect_rings` / `rank_kingpins` treat them exactly as scam
incidents) linked to identifier nodes they share. The identifiers are the
individuating hard connections of counterfeit circulation:

    serial          -> "serial"  node   (the reused plate signature -- the ring link)
    courier_account -> "account" node   (the launderer banking proceeds -- the bridge)

A seizure POINT / denomination / face value is deliberately NOT a node: those are
popularity, not identity, and linking on them would forge false edges on the
proof surface (the same rule that keeps amount and url out of the scam graph).
"""
from __future__ import annotations

import networkx as nx

from src.counterfeit.generate import SeizureRecord

_NODE_PREFIX = {"serial": "serial", "courier_account": "account"}


def build_seizure_graph(seizures: list[SeizureRecord]) -> nx.Graph:
    g = nx.Graph()
    for s in seizures:
        inode = f"incident:{s.report_id}"
        g.add_node(
            inode,
            kind="incident",
            report_id=s.report_id,
            timestamp=s.timestamp,
            scam_type=s.verdict.scam_type,
            is_scam=True,
            amount=s.face_value,
        )
        for field, value in (("serial", s.serial),
                             ("courier_account", s.courier_account)):
            if not value:
                continue
            node = f"{_NODE_PREFIX[field]}:{value}"
            if node not in g:
                g.add_node(node, kind=_NODE_PREFIX[field])
            g.add_edge(inode, node, role=field)
    return g
