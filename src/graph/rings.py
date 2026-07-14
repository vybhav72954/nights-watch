"""Layer 1 -- deterministic ring detection: connected components of the
incident<->identifier graph. No ML, no p-values -- this is the auditable
evidence layer (docs/REPORT_SCHEMA.md §6, docs/SOLUTION_DESIGN.md §3).
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class Ring:
    ring_id: str
    incident_ids: frozenset[str]
    identifier_nodes: frozenset[str]
    # How this ring was detected. Carried on the ring itself, not left to the
    # caller to remember, because the evidence pack stamps these into a
    # court-facing methodology block: a pack that says "hub_degree_cap: null"
    # for a ring actually found at 40 misstates how the evidence was derived,
    # and no amount of docstring prevents a caller forgetting the kwarg.
    hub_degree_cap: int | None = None
    min_incidents: int = 2

    @property
    def size(self) -> int:
        return len(self.incident_ids)


def hub_nodes(g: nx.Graph, degree_cap: int) -> set[str]:
    """Identifier nodes touched by more incidents than `degree_cap` -- e.g. a
    popular payee (Swiggy) every citizen's incident happens to touch. High
    degree alone means "popular", not "ring": letting these nodes form ring
    edges is the #1 failure mode of naive graph fraud detection (see the
    legit-high-degree-hub guardrail, docs/SOLUTION_DESIGN.md §4)."""
    return {
        n for n, data in g.nodes(data=True)
        if data["kind"] != "incident" and g.degree(n) > degree_cap
    }


def detect_rings(
    g: nx.Graph, min_incidents: int = 2, hub_degree_cap: int | None = None,
) -> list[Ring]:
    """Connected components with >= `min_incidents` incidents.

    A component of exactly one incident means that incident shares no
    identifier with anyone else -- not a ring. `hub_degree_cap`, if set,
    excludes hub nodes (see `hub_nodes`) before computing components so a
    popular merchant can't silently fuse thousands of unrelated incidents into
    one false "ring". Rings are returned largest-first with stable `R0000...`
    ids re-assigned after sorting (demo-friendly: R0000 is always the biggest).
    """
    working = g
    if hub_degree_cap is not None:
        hubs = hub_nodes(g, hub_degree_cap)
        if hubs:
            working = g.copy()
            working.remove_nodes_from(hubs)

    candidates = []
    for component in nx.connected_components(working):
        incidents = frozenset(n for n in component if working.nodes[n]["kind"] == "incident")
        if len(incidents) >= min_incidents:
            identifiers = frozenset(component) - incidents
            candidates.append((incidents, identifiers))

    candidates.sort(key=lambda pair: len(pair[0]), reverse=True)
    return [
        Ring(f"R{i:04d}", incidents, identifiers,
             hub_degree_cap=hub_degree_cap, min_incidents=min_incidents)
        for i, (incidents, identifiers) in enumerate(candidates)
    ]
