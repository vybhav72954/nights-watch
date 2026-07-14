"""Tests for src/graph -- Layer 1 rings (build.py, rings.py) and Layer 2
kingpin centrality (kingpin.py). See docs/REPORT_SCHEMA.md §6, CLAUDE.md §4.2."""
from __future__ import annotations

from src.graph import build_graph, detect_rings, rank_kingpins
from src.schema import Report


def _report(report_id, *, payee_upi=None, account=None, ifsc=None, device_hint=None,
            extraction_confidence=0.9, is_scam=True, scam_type="digital_arrest"):
    return Report.model_validate({
        "report_id": report_id,
        "timestamp": "2026-07-07T10:00:00+05:30",
        "channel": "sms",
        "raw_text": "…",
        "verdict": {"is_scam": is_scam, "confidence": 0.9, "scam_type": scam_type},
        "entities": {
            "payee_upi": [payee_upi] if payee_upi else [],
            "account": [account] if account else [],
            "ifsc": [ifsc] if ifsc else [],
            "device_hint": device_hint,
        },
        "extraction_confidence": extraction_confidence,
    })


# ── build_graph ───────────────────────────────────────────────────────────────

def test_shared_upi_links_two_incidents():
    reports = [_report("a", payee_upi="mule@okaxis"), _report("b", payee_upi="mule@okaxis")]
    g = build_graph(reports)
    assert g.has_edge("incident:a", "upi:mule@okaxis")
    assert g.has_edge("incident:b", "upi:mule@okaxis")
    import networkx as nx
    assert nx.node_connected_component(g, "incident:a") == {"incident:a", "incident:b", "upi:mule@okaxis"}


def test_low_confidence_reports_excluded():
    reports = [_report("a", payee_upi="mule@okaxis", extraction_confidence=0.1)]
    g = build_graph(reports, min_extraction_confidence=0.5)
    assert g.number_of_nodes() == 0


def test_account_and_ifsc_share_node_kind_but_distinct_ids():
    r = _report("a", account="50100123456789", ifsc="HDFC0001234")
    g = build_graph([r])
    assert g.nodes["account:50100123456789"]["kind"] == "account"
    assert g.nodes["account:HDFC0001234"]["kind"] == "account"
    assert "account:50100123456789" != "account:HDFC0001234"


# ── Layer 1: detect_rings ────────────────────────────────────────────────────

def test_ring_forms_on_shared_identifier():
    reports = [_report(i, payee_upi="mule@okaxis") for i in "abc"]
    g = build_graph(reports)
    rings = detect_rings(g)
    assert len(rings) == 1
    assert rings[0].incident_ids == frozenset({"incident:a", "incident:b", "incident:c"})


def test_isolated_incident_is_not_a_ring():
    reports = [_report("a", payee_upi="lone@okaxis")]
    g = build_graph(reports)
    assert detect_rings(g) == []


def test_hub_guardrail_prevents_false_merge():
    # 10 unrelated incidents all pay the same popular merchant (a "Swiggy" hub) --
    # no other shared identifier between them.
    hub_reports = [_report(f"legit{i}", payee_upi="swiggy@ybl") for i in range(10)]
    # 2 incidents form a genuine ring: they share the hub AND a second identifier.
    ring_reports = [
        _report("ring0", payee_upi="swiggy@ybl", account="MULEACC01"),
        _report("ring1", payee_upi="swiggy@ybl", account="MULEACC01"),
    ]
    g = build_graph(hub_reports + ring_reports)

    # without a cap, the hub fuses all 12 incidents into one false "ring"
    uncapped = detect_rings(g)
    assert len(uncapped) == 1
    assert uncapped[0].size == 12

    # with the hub capped, only the incidents sharing a SECOND identifier survive
    capped = detect_rings(g, hub_degree_cap=5)
    assert len(capped) == 1
    assert capped[0].incident_ids == frozenset({"incident:ring0", "incident:ring1"})


# ── Layer 2: rank_kingpins ────────────────────────────────────────────────────

def test_kingpin_bridges_rings_hub_capped_out_of_layer1():
    # ring A: two incidents share upi X. ring B: two incidents share upi Y.
    # ALL FOUR also share one device -- a coordinator's front, reused across
    # otherwise-unrelated rings. Capped out of Layer 1 (degree 4 > cap 3) so
    # rings stay legally separate; Layer 2 should surface the device as the
    # top-ranked, cross-ring lead.
    reports = [
        _report("a", payee_upi="frontX@okaxis", device_hint="deviceZ"),
        _report("b", payee_upi="frontX@okaxis", device_hint="deviceZ"),
        _report("c", payee_upi="frontY@okaxis", device_hint="deviceZ"),
        _report("d", payee_upi="frontY@okaxis", device_hint="deviceZ"),
    ]
    g = build_graph(reports)

    rings = detect_rings(g, hub_degree_cap=3)
    assert len(rings) == 2  # kept separate -- device excluded as a ring-forming edge

    scores = rank_kingpins(g, rings)
    top = scores[0]
    assert top.node == "device:deviceZ"
    assert top.ring_ids == frozenset({r.ring_id for r in rings})  # bridges BOTH rings


def test_rank_kingpins_empty_without_rings():
    reports = [_report("a", payee_upi="lone@okaxis")]
    g = build_graph(reports)
    assert rank_kingpins(g, detect_rings(g)) == []


def test_incidents_excluded_from_kingpin_ranking_by_default():
    reports = [_report(i, payee_upi="mule@okaxis") for i in "abc"]
    g = build_graph(reports)
    rings = detect_rings(g)
    scores = rank_kingpins(g, rings)
    assert all(s.kind != "incident" for s in scores)
    scores_with_incidents = rank_kingpins(g, rings, include_incidents=True)
    assert any(s.kind == "incident" for s in scores_with_incidents)
