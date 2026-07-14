"""Layer 2 -- kingpin prioritisation: centrality across rings. A ranked LEAD,
explicitly NOT proof (docs/REPORT_SCHEMA.md §6, CLAUDE.md §4.3).

Layer 1 rings are connected components, which are disjoint by construction --
so "central across rings" can't mean literal cross-component reach unless
Layer 2 looks at a broader graph than Layer 1 used. It does, deliberately:
`ring_union_graph` restores the hub-capped identifier nodes Layer 1 excluded
(see `rings.hub_nodes`) for every ring's incidents. A coordinator who reuses
one device/phone as a front across otherwise-unrelated rings is exactly the
kind of node that mechanism excludes from Layer-1 evidence (rightly -- fan-in
alone isn't proof) and Layer 2 exists precisely to surface as a lead.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from src.graph.rings import Ring


@dataclass(frozen=True)
class KingpinScore:
    node: str
    kind: str
    score: float
    degree: int
    betweenness: float
    eigenvector: float
    ring_ids: frozenset[str]


def ring_union_graph(g: nx.Graph, rings: list[Ring]) -> nx.Graph:
    """Induced subgraph of the FULL graph `g` (not hub-pruned) spanning every
    ring's incidents plus everything they touch. Deliberately re-admits any
    hub-capped identifier a ring's incidents still connect to in `g`."""
    incidents = {n for r in rings for n in r.incident_ids}
    neighbours = {nb for inc in incidents if inc in g for nb in g.neighbors(inc)}
    return g.subgraph(incidents | neighbours).copy()


def _node_ring_ids(union: nx.Graph, rings: list[Ring]) -> dict[str, frozenset[str]]:
    """Which ring(s) each node in `union` touches, keyed off ring incidents --
    not `Ring.identifier_nodes`, so a hub-capped bridge node still picks up
    membership in every ring it connects to."""
    node_rings: dict[str, set[str]] = {n: set() for n in union.nodes()}
    for r in rings:
        for inc in r.incident_ids:
            if inc not in union:
                continue
            node_rings[inc].add(r.ring_id)
            for nb in union.neighbors(inc):
                node_rings[nb].add(r.ring_id)
    return {n: frozenset(rs) for n, rs in node_rings.items()}


def _min_max_normalise(values: dict[str, float], nodes: list[str]) -> dict[str, float]:
    vals = [values[n] for n in nodes]
    lo, hi = min(vals), max(vals)
    span = hi - lo
    return {n: ((values[n] - lo) / span if span > 0 else 0.0) for n in nodes}


def rank_kingpins(
    g: nx.Graph, rings: list[Ring], top_k: int | None = None, include_incidents: bool = False,
) -> list[KingpinScore]:
    """Rank nodes by centrality (degree + betweenness + eigenvector, min-max
    normalised then averaged) over `ring_union_graph(g, rings)`. Identifier
    nodes only by default -- a kingpin claim names a person/identifier, not a
    single report; pass `include_incidents=True` to score incidents too."""
    if not rings:
        return []

    union = ring_union_graph(g, rings)
    nodes = [
        n for n, d in union.nodes(data=True)
        if include_incidents or d["kind"] != "incident"
    ]
    if not nodes:
        return []

    degree = dict(union.degree())
    betweenness = nx.betweenness_centrality(union)
    try:
        eigenvector = nx.eigenvector_centrality(union, max_iter=1000)
    except nx.PowerIterationFailedConvergence:
        eigenvector = {n: 0.0 for n in union.nodes()}

    nd = _min_max_normalise(degree, nodes)
    nb = _min_max_normalise(betweenness, nodes)
    ne = _min_max_normalise(eigenvector, nodes)
    node_ring_ids = _node_ring_ids(union, rings)

    scores = [
        KingpinScore(
            node=n,
            kind=union.nodes[n]["kind"],
            score=(nd[n] + nb[n] + ne[n]) / 3,
            degree=degree[n],
            betweenness=betweenness[n],
            eigenvector=eigenvector[n],
            ring_ids=node_ring_ids[n],
        )
        for n in nodes
    ]
    scores.sort(key=lambda s: s.score, reverse=True)
    return scores[:top_k] if top_k else scores
