"""Report list -> the incident<->identifier bipartite graph (docs/REPORT_SCHEMA.md §6).

Nodes: `incident:<report_id>` plus one node per distinct identifier value
(`upi:…`, `phone:…`, `account:…`, `device:…`). Edges: `incident -uses-> identifier`.
Two incidents are linked iff they share an identifier node -- a hard connection.
Pure networkx; no ML, no thresholds -- this is the substrate Layer 1 runs on.
"""
from __future__ import annotations

import networkx as nx

from src.schema import Report

# entities.account and entities.ifsc both resolve to the "account" node kind
# (docs/REPORT_SCHEMA.md §6) -- an account number and its IFSC describe the
# same underlying bank account, not two link types.
_NODE_PREFIX = {
    "payee_upi": "upi",
    "phone": "phone",
    "account": "account",
    "ifsc": "account",
    "device_hint": "device",
}


def _incident_node(report_id: str) -> str:
    return f"incident:{report_id}"


def _identifier_node(kind: str, value: str) -> str:
    return f"{_NODE_PREFIX[kind]}:{value}"


def _identifiers(report: Report) -> list[tuple[str, str]]:
    """(entity-field, value) pairs for every identifier a report carries."""
    e = report.entities
    pairs = [(k, v) for k in ("payee_upi", "phone", "account", "ifsc") for v in getattr(e, k)]
    if e.device_hint:
        pairs.append(("device_hint", e.device_hint))
    return pairs


def build_graph(reports: list[Report], min_extraction_confidence: float = 0.0) -> nx.Graph:
    """Build the incident<->identifier graph.

    Reports below `min_extraction_confidence` are excluded (docs/REPORT_SCHEMA.md
    §8 -- keeps weak extractions from polluting ring structure).
    """
    g = nx.Graph()
    for report in reports:
        if not report.is_graph_eligible(min_extraction_confidence):
            continue
        inode = _incident_node(report.report_id)
        g.add_node(
            inode,
            kind="incident",
            report_id=report.report_id,
            timestamp=report.timestamp,
            scam_type=report.verdict.scam_type,
            is_scam=report.verdict.is_scam,
            amount=report.entities.amount,
        )
        for entity_field, value in _identifiers(report):
            node = _identifier_node(entity_field, value)
            if node not in g:
                g.add_node(node, kind=_NODE_PREFIX[entity_field])
            g.add_edge(inode, node, role=entity_field)
    return g
