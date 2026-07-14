"""Tests for src/evidence/leadtime.py -- the G1 lead-time replay (CLAUDE.md
§15). Checks the counterfactual against the seeded network's known answer
key, the demo's "flagged at report 2; N-2 preventable" headline, the
documented undetected-ring exception, and the purity guard that stops an
uncapped hub from falsely crediting a glued-together ring with an early hit.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.evidence import (
    DEMO_HUB_DEGREE_CAP,
    LeadTimeReplay,
    lead_time_headline,
    replay_lead_time,
)
from src.generate.network import DEMO_RING_SIZES, generate_network
from src.schema import Report


def _network(seed=0, ring_sizes=(4,) * 6, kingpin_ring_count=3, n_victims=40):
    return generate_network(seed=seed, ring_sizes=ring_sizes,
                            kingpin_ring_count=kingpin_ring_count, n_victims=n_victims)


def _mk_report(report_id: str, upi: str, ring_id: str, timestamp: datetime, phone: list[str] | None = None) -> Report:
    return Report.model_validate({
        "report_id": report_id,
        "timestamp": timestamp.isoformat(),
        "channel": "sms",
        "raw_text": "test report",
        "verdict": {"is_scam": True, "confidence": 0.9, "scam_type": "other", "red_flags": []},
        "entities": {"payee_upi": [upi], "phone": phone or []},
        "extraction_confidence": 0.9,
        "_gt": {"ring_id": ring_id, "is_kingpin_incident": False},
    })


def test_every_planted_ring_on_the_seeded_network_is_detected_at_its_second_report():
    # kingpin_ring_count=0 isolates the pure mule-UPI-linkage claim (CLAUDE.md
    # G1: "linkage on a shared mule UPI means detection at the ring's 2nd
    # report"). A kingpin ring's cross-ring bridging phone is a second,
    # separate linkage channel that can legitimately delay detection until
    # the hub cap excludes it -- covered by the purity-guard test below, not
    # asserted here.
    reports = _network(seed=0, ring_sizes=(4,) * 6, kingpin_ring_count=0, n_victims=40)
    replays = replay_lead_time(reports, hub_degree_cap=10, min_incidents=2)

    assert len(replays) == 6
    for r in replays:
        assert r.detected_at_report == 2, r.ring_id
        assert r.eventual_size == 4
        assert r.victims_after_flag == 2
        assert r.detected_at_timestamp is not None


def test_a_kingpin_rings_cross_ring_bridging_phone_can_delay_but_not_prevent_detection():
    # With kingpin rings present, the shared bridging phone can glue multiple
    # rings together before the hub cap's degree threshold is reached,
    # pushing pure detection past k=2 -- an honest, documented effect (not a
    # bug): every ring must still eventually be detected once the cap
    # excludes the bridge.
    reports = _network(seed=0, ring_sizes=(4,) * 6, kingpin_ring_count=3, n_victims=40)
    replays = replay_lead_time(reports, hub_degree_cap=10, min_incidents=2)

    assert len(replays) == 6
    for r in replays:
        assert r.detected_at_report is not None, r.ring_id
        assert r.detected_at_report >= 2
        assert r.eventual_size == 4


def test_victims_after_flag_is_always_eventual_size_minus_detected_at_report():
    reports = _network(seed=1, ring_sizes=(5,) * 4, kingpin_ring_count=2, n_victims=30)
    replays = replay_lead_time(reports, hub_degree_cap=10, min_incidents=2)
    assert replays  # sanity: the network actually planted rings
    for r in replays:
        if r.detected_at_report is None:
            assert r.victims_after_flag is None
            assert r.detected_at_timestamp is None
        else:
            assert r.victims_after_flag == r.eventual_size - r.detected_at_report


def test_lead_time_headline_is_the_demo_closer_on_the_seeded_corpus_itself():
    # The closer is now measured on the SAME world the app draws
    # (`core.seeded_reports`), at the SAME cap -- so "flagged at report 2; 28
    # preventable" is a property of the demo's own intelligence base, about the
    # very ring the citizen's report joins on the Live page.
    #
    # It used to be measured on a network generated solely for the purpose (one
    # ring, 30 victims, no kingpin), because the old cap of 10 made a ring bigger
    # than 10 undetectable in batch -- its own mule UPI would exceed the cap and
    # be pruned as a hub. So the seeded world could not host the ring its own
    # closer was about, and a judge saw a ring of 5 on the hero screen and a ring
    # of 30 on the lead-time page.
    reports = generate_network(seed=0)
    replays = replay_lead_time(reports, hub_degree_cap=DEMO_HUB_DEGREE_CAP, min_incidents=2)

    assert len(replays) == len(DEMO_RING_SIZES)
    biggest = max(replays, key=lambda r: r.eventual_size)
    assert biggest.eventual_size == max(DEMO_RING_SIZES) == 30
    assert biggest.detected_at_report == 2
    assert biggest.victims_after_flag == 28

    assert lead_time_headline(replays) == "flagged at report 2; 28 subsequent victims were preventable."


def test_the_kingpin_bridge_delays_a_later_ring_on_the_demo_corpus_but_never_loses_it():
    # The honest cost of the kingpin story, on the demo corpus, stated rather
    # than hidden. R0000's window comes first, so while its reports arrive the
    # bridging phone touches only R0000 and its component stays pure -- flagged
    # at report 2. R0001's reports then arrive already glued to R0000's 30 via
    # that phone (still under the cap), so R0001 cannot be credited until the
    # phone's degree crosses the cap and Layer 1 drops it as a hub. Every ring
    # is still detected in the end.
    replays = {
        r.ring_id: r for r in
        replay_lead_time(generate_network(seed=0), hub_degree_cap=DEMO_HUB_DEGREE_CAP)
    }
    assert all(r.detected_at_report is not None for r in replays.values())
    assert replays["R0000"].detected_at_report == 2
    assert replays["R0001"].detected_at_report > 2


def test_ring_that_never_reaches_min_incidents_is_reported_as_the_documented_exception():
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    reports = [
        _mk_report("lonely1", "lonely@x", "RLONELY", t0),
        _mk_report("pair1", "shared@x", "RPAIR", t0 + timedelta(minutes=1)),
        _mk_report("pair2", "shared@x", "RPAIR", t0 + timedelta(minutes=2)),
    ]
    replays = replay_lead_time(reports, min_incidents=2)
    by_ring = {r.ring_id: r for r in replays}

    assert by_ring["RPAIR"].detected_at_report == 2
    assert by_ring["RLONELY"].eventual_size == 1
    assert by_ring["RLONELY"].detected_at_report is None
    assert by_ring["RLONELY"].victims_after_flag is None
    assert by_ring["RLONELY"].detected_at_timestamp is None


def test_uncapped_hub_glues_a_later_ring_into_an_impure_component_but_the_cap_recovers_it():
    # Two rings that each use their own mule UPI but both also carry one
    # shared high-degree phone (an uncapped payment-gateway-style hub).
    # Ring A's reports arrive first and are pure before the hub ever touches
    # ring B, so A is still detected early even uncapped; ring B's reports
    # only ever arrive already glued to A via the hub, so B must stay
    # undetected uncapped and only recovers once hub_degree_cap excludes the
    # hub node -- exactly the purity guard CLAUDE.md G1 calls for.
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    hub_phone = "+919000000000"
    reports = [
        _mk_report(f"a{i}", "mule_a@x", "RA", t0 + timedelta(minutes=i), phone=[hub_phone])
        for i in range(3)
    ] + [
        _mk_report(f"b{i}", "mule_b@x", "RB", t0 + timedelta(minutes=10 + i), phone=[hub_phone])
        for i in range(3)
    ]

    uncapped = replay_lead_time(reports, hub_degree_cap=None, min_incidents=2)
    by_ring_uncapped = {r.ring_id: r for r in uncapped}
    assert by_ring_uncapped["RB"].detected_at_report is None

    capped = replay_lead_time(reports, hub_degree_cap=4, min_incidents=2)
    by_ring_capped = {r.ring_id: r for r in capped}
    assert by_ring_capped["RA"].detected_at_report == 2
    assert by_ring_capped["RB"].detected_at_report == 2
