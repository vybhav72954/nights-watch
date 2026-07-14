"""Tests for src/generate/messages.py -- the answer-key text corpus.

Beyond checking the generator's own fields, these confirm the corpus actually
produces the ring/kingpin structure src/graph is built to recover -- generation
and detection are tested together, not just each in isolation.
"""
from __future__ import annotations

from src.generate.messages import KINGPIN_PHONE, LEGIT_HUB_UPI, generate_messages, train_eval_split
from src.graph import build_graph, detect_rings, rank_kingpins

KINGPIN_PHONE_NORMALISED = f"+91{KINGPIN_PHONE}"


def _by_ring(reports):
    rings: dict[str, list] = {}
    for r in reports:
        if r.gt and r.gt.ring_id:
            rings.setdefault(r.gt.ring_id, []).append(r)
    return rings


def test_each_ring_shares_exactly_one_mule_upi():
    reports = generate_messages(seed=0)
    for ring_id, members in _by_ring(reports).items():
        upis = {m.entities.payee_upi[0] for m in members}
        assert upis == {members[0].entities.payee_upi[0]}, ring_id


def test_mule_upis_are_disjoint_across_rings():
    reports = generate_messages(seed=0)
    upi_by_ring = {rid: {m.entities.payee_upi[0] for m in ms} for rid, ms in _by_ring(reports).items()}
    seen = set()
    for upis in upi_by_ring.values():
        assert not (upis & seen)
        seen |= upis


def test_kingpin_rings_share_the_kingpin_phone():
    reports = generate_messages(seed=0, n_rings=6, kingpin_ring_count=3)
    for ring_id, members in _by_ring(reports).items():
        phones = {m.entities.phone[0] for m in members}
        assert len(phones) == 1
        is_kingpin_ring = all(m.gt.is_kingpin_incident for m in members)
        if is_kingpin_ring:
            assert phones == {KINGPIN_PHONE_NORMALISED}
        else:
            assert phones != {KINGPIN_PHONE_NORMALISED}


def test_non_kingpin_ring_phones_are_unique_across_rings():
    reports = generate_messages(seed=0, n_rings=6, kingpin_ring_count=3)
    non_kingpin_phones = [
        ms[0].entities.phone[0] for ms in _by_ring(reports).values() if not ms[0].gt.is_kingpin_incident
    ]
    assert len(non_kingpin_phones) == len(set(non_kingpin_phones))


def test_legit_reports_have_no_ring_and_are_not_scam():
    reports = generate_messages(seed=0)
    legit = [r for r in reports if r.gt.ring_id is None]
    assert legit
    assert all(not r.verdict.is_scam and r.verdict.scam_type == "legit" for r in legit)
    assert all(not r.gt.is_kingpin_incident for r in legit)


def test_legit_hub_touched_by_a_plausible_share_of_legit_reports():
    reports = generate_messages(seed=0, n_legit=100, legit_hub_share=0.4)
    legit = [r for r in reports if r.gt.ring_id is None]
    hub_hits = sum(1 for r in legit if r.entities.payee_upi == [LEGIT_HUB_UPI])
    assert 0.25 * len(legit) < hub_hits < 0.55 * len(legit)


def test_planted_rings_recoverable_as_exact_connected_components():
    reports = generate_messages(seed=0)
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=8)  # excludes the ~40%-of-100 legit hub
    detected_sets = {ring.incident_ids for ring in rings}
    for ring_id, members in _by_ring(reports).items():
        expected = frozenset(f"incident:{m.report_id}" for m in members)
        assert expected in detected_sets, ring_id


def test_kingpin_phone_ranks_top_and_bridges_exactly_the_kingpin_rings():
    reports = generate_messages(seed=0, n_rings=6, kingpin_ring_count=3)
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=8)
    scores = rank_kingpins(g, rings)
    top = scores[0]
    assert top.node == f"phone:{KINGPIN_PHONE_NORMALISED}"

    bridged = {ring.ring_id: ring for ring in rings if ring.ring_id in top.ring_ids}
    bridged_incidents = {inc for ring in bridged.values() for inc in ring.incident_ids}
    expected_incidents = {
        f"incident:{r.report_id}" for r in reports if r.gt.is_kingpin_incident
    }
    assert bridged_incidents == expected_incidents


def test_train_eval_split_is_disjoint_and_covers_everything():
    reports = generate_messages(seed=0)
    train, eval_ = train_eval_split(reports, eval_frac=0.2, seed=1)
    train_ids = {r.report_id for r in train}
    eval_ids = {r.report_id for r in eval_}
    assert not (train_ids & eval_ids)
    assert train_ids | eval_ids == {r.report_id for r in reports}
    assert eval_ids  # non-empty for a reasonably sized corpus
