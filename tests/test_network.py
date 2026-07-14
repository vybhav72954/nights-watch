"""Tests for src/generate/network.py -- the pre-seeded scam network.

`generate_network` reuses the vendored engine's `inject_ring` for the windowed
fan-in structure; these tests confirm the post-processing (fresh mule UPIs,
planted kingpin phone) survives that reuse and produces a graph src/graph
recovers cleanly -- generation and detection tested together.
"""
from __future__ import annotations

from src.evidence import DEMO_HUB_DEGREE_CAP
from src.generate.io import answer_key
from src.generate.network import (
    DEMO_RING_SIZES,
    KINGPIN_PHONE,
    LEGIT_HUB_UPI,
    SCAM_AMOUNT_RANGE,
    generate_network,
)
from src.graph import build_graph, detect_rings, rank_kingpins

KINGPIN_PHONE_NORMALISED = f"+91{KINGPIN_PHONE}"


def _by_ring(reports):
    rings: dict[str, list] = {}
    for r in reports:
        if r.gt and r.gt.ring_id:
            rings.setdefault(r.gt.ring_id, []).append(r)
    return rings


def test_ring_count_and_size_match_params():
    reports = generate_network(seed=0, ring_sizes=(4,) * 6)
    rings = _by_ring(reports)
    assert len(rings) == 6
    assert all(len(members) == 4 for members in rings.values())


def test_rings_are_trimmed_to_exactly_the_requested_sizes():
    # The engine's `inject_ring` only does uniform rings, so `_plant_rings`
    # over-injects and trims. Unequal sizes are the point: with every ring the
    # same size, "the largest ring" is a coin toss and the demo's join-the-
    # biggest-ring path never gets exercised.
    reports = generate_network(seed=0, ring_sizes=(7, 3, 2))
    assert sorted((len(m) for m in _by_ring(reports).values()), reverse=True) == [7, 3, 2]


def test_the_demo_network_has_the_degree_hierarchy_the_cap_depends_on():
    # The seeded world is only coherent if the hub cap fits in the gap between
    # the biggest ring and the kingpin's bridging phone. Everything else in the
    # demo -- ring recovery, the kingpin lead, the lead-time replay, the slider
    # curve -- is downstream of these five numbers holding this order.
    g = build_graph(generate_network(seed=0))
    degree = {n: g.degree(n) for n, d in g.nodes(data=True) if d["kind"] != "incident"}

    biggest_ring = degree["upi:mule00@okaxis"]
    kingpin = degree[f"phone:{KINGPIN_PHONE_NORMALISED}"]
    merchants = min(d for n, d in degree.items() if "merchant" in n)
    hub = degree[f"upi:{LEGIT_HUB_UPI}"]

    assert biggest_ring == max(DEMO_RING_SIZES) == 30
    assert biggest_ring < DEMO_HUB_DEGREE_CAP < kingpin < merchants < hub

    # ...and enough slack above the biggest ring to survive a live demo: every
    # report a judge sends naming mule00@okaxis adds 1 to its degree, and the
    # ring drops off Layer 1 the moment it crosses the cap.
    assert DEMO_HUB_DEGREE_CAP - biggest_ring >= 5


def test_scam_reports_are_priced_as_scams_not_as_legit_traffic():
    # `inject_ring` samples `amount` from the legit pool (the engine's
    # controlled-benchmark invariant); `_plant_rings` re-draws it, because the
    # amount is rendered into the message and summed into the ring's reported
    # loss -- a "digital arrest" demanding Rs.1,847 misstates the harm and reads
    # as obviously fake.
    reports = generate_network(seed=0)
    scam = [r for r in reports if r.gt.ring_id is not None]
    legit = [r for r in reports if r.gt.ring_id is None]

    lo, hi = SCAM_AMOUNT_RANGE
    assert all(lo <= r.entities.amount < hi for r in scam)
    assert max(r.entities.amount for r in legit) < lo


def test_each_ring_has_a_fresh_unique_mule_upi():
    reports = generate_network(seed=0)
    upi_by_ring = {rid: {m.entities.payee_upi[0] for m in ms} for rid, ms in _by_ring(reports).items()}
    assert all(len(upis) == 1 for upis in upi_by_ring.values())
    seen = set()
    for upis in upi_by_ring.values():
        assert not (upis & seen)
        seen |= upis


def test_kingpin_ring_count_matches_param():
    reports = generate_network(seed=0, kingpin_ring_count=3)
    kingpin_rings = {rid for rid, ms in _by_ring(reports).items() if ms[0].gt.is_kingpin_incident}
    assert len(kingpin_rings) == 3
    for rid in kingpin_rings:
        assert all(m.entities.phone == [KINGPIN_PHONE_NORMALISED] for m in _by_ring(reports)[rid])


def test_the_kingpins_rings_run_different_pretexts():
    # The Layer 2 claim on stage is "one controller, three different scams", so
    # it has to be true of the data. Ring 0 is digital_arrest to match the hero
    # message the demo pastes in.
    reports = generate_network(seed=0)
    by_ring = _by_ring(reports)
    kingpin_rings = sorted(rid for rid, ms in by_ring.items() if ms[0].gt.is_kingpin_incident)

    types = [{m.verdict.scam_type for m in by_ring[rid]} for rid in kingpin_rings]
    assert all(len(t) == 1 for t in types)  # one pretext per ring
    assert len({next(iter(t)) for t in types}) == 3  # ...and all three differ
    assert by_ring["R0000"][0].verdict.scam_type == "digital_arrest"


def test_non_kingpin_rings_carry_no_phone():
    reports = generate_network(seed=0, kingpin_ring_count=3)
    for rid, members in _by_ring(reports).items():
        if not members[0].gt.is_kingpin_incident:
            assert all(m.entities.phone == [] for m in members)


def test_legit_background_has_high_degree_hub():
    reports = generate_network(seed=0, n_victims=500, legit_hub_share=0.4)
    legit = [r for r in reports if r.gt.ring_id is None]
    assert legit
    hub_hits = sum(1 for r in legit if r.entities.payee_upi == [LEGIT_HUB_UPI])
    assert hub_hits > max(DEMO_RING_SIZES)  # a hub, not merely another ring


def test_answer_key_matches_report_gt():
    reports = generate_network(seed=0)
    ak = answer_key(reports)
    assert len(ak["rings"]) == len(DEMO_RING_SIZES)
    assert sorted((v["size"] for v in ak["rings"].values()), reverse=True) == list(DEMO_RING_SIZES)
    assert len(ak["kingpin_report_ids"]) == sum(DEMO_RING_SIZES[:3])


def test_planted_rings_recoverable_and_kingpin_bridges_them():
    reports = generate_network(seed=0)
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=DEMO_HUB_DEGREE_CAP)
    assert len(rings) == len(DEMO_RING_SIZES)

    detected_sets = {ring.incident_ids for ring in rings}
    for ring_id, members in _by_ring(reports).items():
        expected = frozenset(f"incident:{m.report_id}" for m in members)
        assert expected in detected_sets, ring_id

    scores = rank_kingpins(g, rings)
    top = scores[0]
    assert top.node == f"phone:{KINGPIN_PHONE_NORMALISED}"
    assert len(top.ring_ids) == 3

    bridged_incidents = {
        inc for ring in rings if ring.ring_id in top.ring_ids for inc in ring.incident_ids
    }
    expected_incidents = {f"incident:{r.report_id}" for r in reports if r.gt.is_kingpin_incident}
    assert bridged_incidents == expected_incidents
