"""Tests for src/evidence -- the Layer 1 proof pack, the Layer 2 lead, the
two guardrails this module owns, and answer-key validation.

Built against the same generators the graph tests already trust
(`src/generate/network.py`, `src/generate/messages.py`) so evidence output is
checked against a known planted answer key, not just shape-asserted.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from src.detector import detect
from src.evidence import (
    DEMO_HUB_DEGREE_CAP,
    adversarial_split_reports,
    build_evidence_pack,
    build_kingpin_leads,
    describe_adversarial_case,
    kingpin_hit_rate,
    kingpin_rank,
    legit_hub_guardrail,
    pairwise_precision_recall,
    precision_recall_curve,
    validate_across_seeds,
    validate_seed,
)
from src.evidence.validate import main as validation_main
from src.generate.messages import LEGIT_HUB_UPI, generate_messages
from src.generate.network import DEMO_RING_SIZES, generate_network
from src.graph import build_graph, detect_rings, rank_kingpins
from src.schema import Report


# ── pack.py (Layer 1) ─────────────────────────────────────────────────────

def _network(seed=0, ring_sizes=DEMO_RING_SIZES, kingpin_ring_count=3):
    reports = generate_network(seed=seed, ring_sizes=ring_sizes,
                               kingpin_ring_count=kingpin_ring_count)
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=DEMO_HUB_DEGREE_CAP)
    reports_by_id = {r.report_id: r for r in reports}
    return reports, g, rings, reports_by_id


def _linking_nodes(g, ring) -> set[str]:
    """The ring's identifiers that two or more of its incidents actually name --
    i.e. the ones that form an edge. The rest link nobody to anybody."""
    return {
        n for n in ring.identifier_nodes
        if sum(1 for nb in g.neighbors(n) if nb in ring.incident_ids) >= 2
    }


def test_evidence_pack_covers_every_incident_and_shared_identifier():
    reports, g, rings, reports_by_id = _network()
    ring = rings[0]
    pack = build_evidence_pack(ring, g, reports_by_id)

    assert pack.ring_id == ring.ring_id
    assert {i.report_id for i in pack.incidents} == {n.split(":", 1)[1] for n in ring.incident_ids}
    assert {f"{s.kind}:{s.value}" for s in pack.shared_identifiers} == _linking_nodes(g, ring)
    assert ring.ring_id in pack.narrative


def test_evidence_pack_omits_an_identifier_that_links_nothing():
    """The demo path: a live report joins a ring by its payee UPI but brings its
    own phone number, which no other report names. That phone forms no edge, so
    it must not be itemised under 'shared identifiers' in a document offered as
    proof -- it would claim a connection that does not exist.

    Invisible to every other test because the seeded rings carry only their mule
    UPI; it takes a *live* report to bring an identifier nobody else names.
    """
    seeded, _, seeded_rings, _ = _network()
    mule = next(n for n in seeded_rings[0].identifier_nodes if n.startswith("upi:")).split(":", 1)[1]
    live = detect(
        f"CBI: arrest warrant issued. Transfer Rs 50,000 to {mule} now. Call +919876543210.",
        channel="whatsapp", use_llm=False,
    )
    reports = seeded + [live]
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=DEMO_HUB_DEGREE_CAP)
    ring = next(r for r in rings if f"incident:{live.report_id}" in r.incident_ids)
    pack = build_evidence_pack(ring, g, {r.report_id: r for r in reports})

    # the phone IS a node of the ring -- it just isn't evidence of linkage
    assert "phone:+919876543210" in ring.identifier_nodes
    values = {s.value for s in pack.shared_identifiers}
    assert "+919876543210" not in values
    assert mule in values
    assert all(len(s.report_ids) >= 2 for s in pack.shared_identifiers)
    assert "+919876543210" not in pack.to_markdown().split("## Shared identifiers")[1]


def test_evidence_pack_json_round_trips():
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    d = json.loads(json.dumps(pack.to_dict()))
    assert d["ring_id"] == pack.ring_id
    assert d["layer"] == 1
    assert d["label"] == "proof"
    assert len(d["incidents"]) == len(pack.incidents)


def test_evidence_pack_to_json_writes_file(tmp_path):
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    out = tmp_path / "pack.json"
    pack.to_json(out)
    assert out.exists()
    assert json.loads(out.read_text(encoding="utf-8"))["ring_id"] == pack.ring_id


def test_evidence_pack_markdown_lists_every_shared_identifier():
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    md = pack.to_markdown()
    for sid in pack.shared_identifiers:
        assert sid.value in md


def test_evidence_pack_to_pdf_writes_a_pdf(tmp_path):
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    out = tmp_path / "pack.pdf"
    pack.to_pdf(out)
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")


def test_evidence_pack_pdf_renders_markup_like_identifier_text_literally(tmp_path):
    # regression for CLAUDE.md B14: Paragraph interprets mini-XML, so tag-like
    # text in an identifier value embedded in the narrative (device_hint is an
    # LLM-supplied free string) crashed the build (unclosed tag) -- or, worse
    # for a court-facing document, silently rendered as formatting. Escaped,
    # it must build and appear literally.
    import dataclasses

    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    poisoned = dataclasses.replace(
        pack, narrative="Ring linked by device <b>AnyDesk & Quick Support across 3 reports"
    )
    out = tmp_path / "poisoned.pdf"
    poisoned.to_pdf(out)  # must not raise
    assert out.read_bytes().startswith(b"%PDF")


def test_evidence_pack_pdf_story_includes_per_incident_hashes_and_pack_hash():
    # closes G3's "still open" note: the PDF (the one format meant for print /
    # FIR annexure) used to omit per-incident hashes entirely. Asserted on the
    # flowables rather than the compressed PDF byte stream.
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    texts = [getattr(el, "text", "") for el in pack._pdf_story()]
    for inc in pack.incidents:
        assert any(inc.raw_text_sha256 in t for t in texts)
    assert any(pack.content_sha256 in t for t in texts)


# ── G3: integrity hardening (CLAUDE.md §15) ────────────────────────────────

def test_incident_summary_raw_text_sha256_matches_hashlib():
    import hashlib

    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    inc = pack.incidents[0]
    assert inc.raw_text_sha256 == hashlib.sha256(inc.raw_text.encode("utf-8")).hexdigest()


def test_evidence_pack_content_sha256_is_stable_across_regeneration():
    # Rebuilding from the same report set must reproduce the identical hash --
    # that's the "regenerable byte-identically" claim in `methodology`. The
    # only thing that legitimately differs between the two builds is
    # `generated_at` (wall-clock), which content_sha256 must not depend on.
    reports, g, rings, reports_by_id = _network()
    pack_a = build_evidence_pack(rings[0], g, reports_by_id)
    pack_b = build_evidence_pack(rings[0], g, reports_by_id)
    assert pack_a.content_sha256 == pack_b.content_sha256


def test_evidence_pack_content_sha256_changes_if_an_incidents_text_changes():
    import dataclasses

    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    tampered_incident = dataclasses.replace(pack.incidents[0], raw_text="tampered")
    tampered = dataclasses.replace(
        pack, incidents=(tampered_incident,) + pack.incidents[1:]
    )
    assert tampered.content_sha256 != pack.content_sha256


def test_evidence_pack_methodology_records_algorithm_and_the_detect_rings_parameters():
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    assert "connected components" in pack.methodology["algorithm"]
    assert pack.methodology["parameters"] == {
        "hub_degree_cap": DEMO_HUB_DEGREE_CAP, "min_incidents": 2,
    }
    assert pack.methodology["code_version"]  # non-empty, even if "unknown"


def test_evidence_pack_cannot_misstate_the_parameters_its_ring_was_detected_with():
    # The methodology block is a court-facing claim about HOW the ring was
    # derived, so it must track the actual `detect_rings` call and not whatever
    # the caller of `build_evidence_pack` happens to say. It used to be caller-
    # supplied kwargs defaulting to detect_rings' defaults: every pack built
    # without them certified "hub_degree_cap: null" (no hub cap applied) for a
    # ring found at 40 -- and this suite's own tests asserted 10.
    reports = generate_network(seed=0)
    g = build_graph(reports)
    for cap in (DEMO_HUB_DEGREE_CAP, 60, None):
        rings = detect_rings(g, hub_degree_cap=cap, min_incidents=2)
        pack = build_evidence_pack(rings[0], g, {r.report_id: r for r in reports})
        assert pack.methodology["parameters"]["hub_degree_cap"] == cap


def test_evidence_pack_certificate_references_bsa_2023_section_63():
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    cert = pack.certificate
    assert "63" in cert["statute"]
    assert "Bharatiya Sakshya Adhiniyam" in cert["statute"]
    assert cert["content_sha256"] == pack.content_sha256
    assert "PLACEHOLDER" in cert["status"]


def test_evidence_pack_json_round_trip_includes_hashes_methodology_and_certificate():
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    d = json.loads(json.dumps(pack.to_dict()))
    assert d["content_sha256"] == pack.content_sha256
    assert d["methodology"]["parameters"]["hub_degree_cap"] == DEMO_HUB_DEGREE_CAP
    assert d["certificate"]["statute"] == pack.certificate["statute"]
    assert all("raw_text_sha256" in inc for inc in d["incidents"])


def test_evidence_pack_markdown_includes_hashes_methodology_and_certificate():
    reports, g, rings, reports_by_id = _network()
    pack = build_evidence_pack(rings[0], g, reports_by_id)
    md = pack.to_markdown()
    assert pack.content_sha256 in md
    assert pack.incidents[0].raw_text_sha256 in md
    assert "## Methodology" in md
    assert "## Certificate" in md
    assert "Section 63" in md


# ── lead.py (Layer 2) ─────────────────────────────────────────────────────

def test_kingpin_lead_bridges_exactly_the_kingpin_rings():
    reports, g, rings, _ = _network(kingpin_ring_count=3)
    scores = rank_kingpins(g, rings)
    leads = build_kingpin_leads(scores, rings, top_k=3)

    top = leads[0]
    assert len(top.bridged_ring_ids) == 3
    assert top.label == "lead"
    assert "NOT legal proof" in top.disclaimer
    assert str(len(top.bridged_ring_ids)) in top.narrative


def test_kingpin_lead_dict_is_json_safe():
    reports, g, rings, _ = _network()
    scores = rank_kingpins(g, rings)
    d = build_kingpin_leads(scores, rings, top_k=1)[0].to_dict()
    json.dumps(d)  # must not raise
    assert d["layer"] == 2
    assert d["label"] == "lead"


# ── guardrails.py ─────────────────────────────────────────────────────────

def test_legit_hub_guardrail_passes_on_the_planted_hub():
    reports = generate_messages(seed=0, n_legit=100, legit_hub_share=0.4)
    g = build_graph(reports)
    hub_node = f"upi:{LEGIT_HUB_UPI}"
    result = legit_hub_guardrail(g, hub_node, hub_degree_cap=8)
    assert result.passed
    assert "degree" in result.detail


def test_legit_hub_guardrail_fails_loudly_if_hub_missing():
    reports = generate_messages(seed=0, n_legit=10, legit_hub_share=0.0)
    g = build_graph(reports)
    try:
        legit_hub_guardrail(g, "upi:nonexistent@ybl", hub_degree_cap=8)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_adversarial_case_layer1_misses_layer2_bridges():
    reports = adversarial_split_reports(n_victims=12, seed=0)
    result = describe_adversarial_case(reports, hub_degree_cap=8)
    assert result.passed, result.detail
    assert "did NOT find" in result.detail


def test_the_adversarial_scenario_must_out_scale_the_cap_it_is_described_at():
    # The app runs this guardrail at DEMO_HUB_DEGREE_CAP, so the scenario's own
    # scale has to stay above it -- the whole tension is that the shared device
    # looks like a hub. Under-scale it and the device survives the cap, Layer 1
    # simply links the victims, and the limitation the guardrail exists to state
    # is quietly no longer true. Its default tracks the cap; 12 (the old default,
    # tuned to a cap of 10) does not.
    at_scale = describe_adversarial_case(
        adversarial_split_reports(seed=0), hub_degree_cap=DEMO_HUB_DEGREE_CAP,
    )
    assert at_scale.passed, at_scale.detail
    assert "excluded as a hub" in at_scale.detail

    under_scale = describe_adversarial_case(
        adversarial_split_reports(n_victims=12, seed=0), hub_degree_cap=DEMO_HUB_DEGREE_CAP,
    )
    assert not under_scale.passed
    assert "NOT excluded" in under_scale.detail  # and it says so, rather than claiming ">"


# ── validate.py ────────────────────────────────────────────────────────────

def test_pairwise_precision_recall_is_perfect_at_the_right_cap():
    reports, g, rings, _ = _network()
    precision, recall, f1 = pairwise_precision_recall(reports, rings)
    assert precision == 1.0
    assert recall == 1.0
    assert f1 == 1.0


def test_precision_recall_curve_degrades_without_the_hub_guardrail():
    reports = generate_messages(seed=0, n_legit=100, legit_hub_share=0.4)
    g = build_graph(reports)
    curve = precision_recall_curve(reports, g, hub_degree_caps=[8, None])
    by_cap = {c.hub_degree_cap: c for c in curve}
    # uncapped: the legit hub fuses unrelated legit reports into false rings,
    # tanking precision relative to a sane cap.
    assert by_cap[8].precision > by_cap[None].precision


def test_kingpin_hit_rate_top1_on_planted_network():
    reports, g, rings, _ = _network(kingpin_ring_count=3)
    scores = rank_kingpins(g, rings)
    assert kingpin_hit_rate(scores, g, reports, k=1)


def _mk_report(report_id: str, upi: str, *, is_kingpin: bool = False) -> Report:
    return Report.model_validate({
        "report_id": report_id,
        "timestamp": datetime(2026, 6, 1, tzinfo=timezone.utc).isoformat(),
        "channel": "sms",
        "raw_text": "test report",
        "verdict": {"is_scam": True, "confidence": 0.9, "scam_type": "other", "red_flags": []},
        "entities": {"payee_upi": [upi]},
        "extraction_confidence": 0.9,
        "_gt": {"ring_id": "RX", "is_kingpin_incident": is_kingpin},
    })


def test_kingpin_rank_excludes_a_non_bridging_neighbour_of_the_kingpin_incident():
    # regression for CLAUDE.md B6: kingpin_rank used to count ANY identifier
    # neighbouring a kingpin incident, including that ring's own mule UPI --
    # not just a genuine cross-ring bridge. Two fully disjoint rings (no
    # shared identifier between them at all) plant no real kingpin; the old
    # code would still report a "hit" via ring A's own UPI.
    reports = [
        _mk_report("a1", "mule_a@x", is_kingpin=True),
        _mk_report("a2", "mule_a@x"),
        _mk_report("b1", "mule_b@x"),
        _mk_report("b2", "mule_b@x"),
    ]
    g = build_graph(reports)
    rings = detect_rings(g)
    scores = rank_kingpins(g, rings)
    assert kingpin_rank(scores, g, reports) is None


# ── validate.py: multi-seed sweep + the slide-8 artifact ──────────────────

def test_validate_seed_is_perfect_on_the_planted_network():
    run = validate_seed(0)
    assert run.n_rings == len(DEMO_RING_SIZES)
    assert run.precision == 1.0
    assert run.recall == 1.0
    assert run.f1 == 1.0
    assert run.kingpin_rank == 1


def test_validate_across_seeds_kingpin_top1_and_ring_recovery_hold():
    # guards the deck's robustness claim mechanism on a fast slice; the full
    # 20-seed number is regenerated by `python -m src.evidence.validate`
    # (measured 20/20 at the time this test was written).
    result = validate_across_seeds(5)
    assert result.n_seeds == 5
    assert [r.seed for r in result.runs] == [0, 1, 2, 3, 4]
    assert result.kingpin_top1_hits == 5
    assert result.kingpin_top1_rate == 1.0
    d = result.to_dict()
    assert d["precision_mean"] == 1.0 and d["precision_sd"] == 0.0
    assert d["recall_mean"] == 1.0 and d["recall_sd"] == 0.0


def test_multi_seed_validation_to_dict_is_json_safe_and_consistent():
    result = validate_across_seeds(2)
    d = json.loads(json.dumps(result.to_dict()))
    assert d["n_seeds"] == len(d["runs"]) == 2
    assert d["kingpin_top1_rate"] == d["kingpin_top1_hits"] / d["n_seeds"]
    assert d["kingpin_ranks"] == [r["kingpin_rank"] for r in d["runs"]]
    assert d["hub_degree_cap"] == DEMO_HUB_DEGREE_CAP


def test_validation_main_writes_json_artifact_and_figure(tmp_path):
    out_path = tmp_path / "validation.json"
    figure_path = tmp_path / "pr_curve.png"
    result = validation_main(
        n_seeds=2, curve_caps=[4, 10, None], out_path=out_path, figure_path=figure_path,
    )
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["multi_seed"]["n_seeds"] == 2
    assert [p["hub_degree_cap"] for p in written["curve"]["points"]] == [4, 10, None]
    # measured-under params recorded -- the ring shape is the claim's context
    assert written["network_params"]["ring_sizes"] == list(DEMO_RING_SIZES)
    assert "code_version" in written
    assert figure_path.exists() and figure_path.stat().st_size > 0
    assert result["multi_seed"] == written["multi_seed"]
