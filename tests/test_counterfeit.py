"""Tests for the counterfeit-circulation re-point (src/counterfeit/).

These guard the reframe made real (CLAUDE.md §3 row 1): the identical Layer 1 /
Layer 2 machinery, re-pointed to FICN roles, recovers a planted counterfeit
circulation ring + its launderer and emits the same evidence pack. Self-
generating (no external download), so they always run.
"""
from __future__ import annotations

import json

from src.counterfeit.generate import (
    FICN_HUB_DEGREE_CAP,
    FICN_KINGPIN_RING_COUNT,
    FICN_RING_SIZES,
    generate_seizures,
)
from src.counterfeit.graph import build_seizure_graph
from src.counterfeit.validate import sample_evidence_pack, validate_across_seeds, validate_seed
from src.evidence.validate import pairwise_precision_recall
from src.graph import detect_rings, rank_kingpins


def test_generate_plants_rings_a_kingpin_bridge_and_isolated_background():
    seizures = generate_seizures(seed=0)
    ring_seizures = [s for s in seizures if s.gt_ring_id is not None]
    assert len(ring_seizures) == sum(FICN_RING_SIZES)

    # The kingpin rings share exactly one courier account (the launderer bridge);
    # non-kingpin rings and background carry none.
    courier_accounts = {s.courier_account for s in seizures if s.courier_account}
    assert len(courier_accounts) == 1
    bridged_rings = {s.gt_ring_id for s in seizures if s.courier_account}
    assert len(bridged_rings) == FICN_KINGPIN_RING_COUNT
    assert all(s.gt_is_kingpin for s in seizures if s.courier_account)

    # Genuine one-off recoveries: every background serial is unique, so they can
    # never cluster -- the false-positive story.
    bg_serials = [s.serial for s in seizures if s.gt_ring_id is None]
    assert len(bg_serials) == len(set(bg_serials))
    assert all(s.courier_account is None for s in seizures if s.gt_ring_id is None)


def test_layer1_recovers_every_planted_circulation_ring_purely():
    seizures = generate_seizures(seed=0)
    g = build_seizure_graph(seizures)
    rings = detect_rings(g, hub_degree_cap=FICN_HUB_DEGREE_CAP)

    # One detected ring per planted ring, and every detected ring is pure (all
    # its seizures trace to a single planted ring id).
    assert len(rings) == len(FICN_RING_SIZES)
    gt_of = {f"incident:{s.report_id}": s.gt_ring_id for s in seizures}
    for ring in rings:
        planted = {gt_of[i] for i in ring.incident_ids}
        assert len(planted) == 1 and None not in planted

    precision, recall, f1 = pairwise_precision_recall(seizures, rings)
    assert (precision, recall, f1) == (1.0, 1.0, 1.0)


def test_kingpin_is_the_cross_ring_courier_account_ranked_first():
    seizures = generate_seizures(seed=0)
    g = build_seizure_graph(seizures)
    rings = detect_rings(g, hub_degree_cap=FICN_HUB_DEGREE_CAP)
    scores = rank_kingpins(g, rings)

    top = scores[0]
    assert top.kind == "account"                    # a courier account, not a serial
    assert len(top.ring_ids) == FICN_KINGPIN_RING_COUNT  # bridges both kingpin rings
    # and it is the shared courier account, capped out of Layer 1 as a hub.
    courier = next(s.courier_account for s in seizures if s.courier_account)
    assert top.node == f"account:{courier}"


def test_the_courier_bridge_is_excluded_from_layer1_but_surfaces_in_layer2():
    # The whole two-layer point: fan-in alone (the bridge) is not proof, so
    # Layer 1 must NOT fuse the kingpin's rings on it -- they stay separate rings.
    seizures = generate_seizures(seed=0)
    g = build_seizure_graph(seizures)
    rings = detect_rings(g, hub_degree_cap=FICN_HUB_DEGREE_CAP)
    courier = next(s.courier_account for s in seizures if s.courier_account)
    for ring in rings:
        assert f"account:{courier}" not in ring.identifier_nodes


def test_multi_seed_robustness_recovers_the_answer_key_every_time():
    multi = validate_across_seeds(5)
    assert multi.kingpin_top1_rate == 1.0
    d = multi.to_dict()
    assert d["precision_mean"] == 1.0 and d["precision_sd"] == 0.0
    assert d["recall_mean"] == 1.0 and d["recall_sd"] == 0.0
    # single-seed run agrees and is json-safe
    run = validate_seed(0)
    json.dumps(run.to_dict())
    assert run.kingpin_rank == 1


def test_evidence_pack_reuses_the_layer1_machinery_for_a_counterfeit_ring():
    ring, pack = sample_evidence_pack(seed=0)

    # The reused pack, on FICN data: hash-stamped, BSA §63 certified, methodology
    # records the exact cap the ring was detected at (read off the Ring, B22).
    assert pack.ring_id == ring.ring_id
    assert pack.content_sha256 and len(pack.content_sha256) == 64
    assert "Bharatiya Sakshya Adhiniyam" in pack.certificate["statute"]
    assert pack.methodology["parameters"]["hub_degree_cap"] == FICN_HUB_DEGREE_CAP

    # The shared identifier that links the ring is the reused plate serial.
    kinds = {s.kind for s in pack.shared_identifiers}
    assert "serial" in kinds
    assert all(len(s.report_ids) >= 2 for s in pack.shared_identifiers)

    # The narrative uses the seizure noun, not "citizen reports" -- a currency
    # seizure is not a scam report, and a court-facing doc must not say it is.
    md = pack.to_markdown()
    assert "seizure records" in md
    assert "citizen reports" not in md


def test_seizure_record_exposes_the_report_read_surface_the_pipeline_consumes():
    s = generate_seizures(seed=0)[0]
    assert s.verdict.scam_type.startswith("counterfeit_inr")
    assert isinstance(s.entities.amount, int)
    assert hasattr(s.gt, "ring_id") and hasattr(s.gt, "is_kingpin_incident")
