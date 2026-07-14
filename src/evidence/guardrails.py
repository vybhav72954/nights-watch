"""The three guardrails that are the actual credibility story
(docs/SOLUTION_DESIGN.md §4): a popular payee must not be flagged as a ring,
a fraudster who rotates identifiers must be handled honestly (partial
recovery, stated as a limitation, not hidden), and threshold control must be
visible (`validate.precision_recall_curve` powers the demo slider; this
module owns the other two).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import networkx as nx
import numpy as np

from src.graph import build_graph, detect_rings, rank_kingpins
from src.graph.rings import Ring
from src.schema import Report


@dataclass(frozen=True)
class GuardrailResult:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def legit_hub_guardrail(
    g: nx.Graph, hub_identifier_node: str, hub_degree_cap: int, min_incidents: int = 2,
) -> GuardrailResult:
    """Proves the guardrail is load-bearing, not decorative: shows the hub
    WOULD merge unrelated incidents into one false "ring" without a degree
    cap, and does NOT once the cap is applied."""
    if hub_identifier_node not in g:
        raise ValueError(f"{hub_identifier_node!r} not in graph")

    uncapped = detect_rings(g, min_incidents=min_incidents, hub_degree_cap=None)
    capped = detect_rings(g, min_incidents=min_incidents, hub_degree_cap=hub_degree_cap)

    uncapped_hub_ring = next((r for r in uncapped if hub_identifier_node in r.identifier_nodes), None)
    capped_hub_ring = next((r for r in capped if hub_identifier_node in r.identifier_nodes), None)

    hub_degree = g.degree(hub_identifier_node)
    passed = capped_hub_ring is None and uncapped_hub_ring is not None and uncapped_hub_ring.size > 2
    detail = (
        f"{hub_identifier_node} has degree {hub_degree} (cap={hub_degree_cap}). "
        f"Without the cap it would fuse {uncapped_hub_ring.size if uncapped_hub_ring else 0} "
        "unrelated incidents into one false ring. With the cap applied, it is excluded from "
        "Layer 1 entirely: popular is not treated as fraudulent."
    )
    return GuardrailResult(name="legit_high_degree_hub", passed=passed, detail=detail)


# ── adversarial split: a fraudster who rotates payee UPI + phone per victim
# (so a bank freeze on one mule account can't be traced to the next) but is
# forced to reuse ONE thing at real fraud-farm scale: a device. The honest
# tension this demonstrates is not "the graph can't see shared infrastructure"
# -- it's that the SAME hub-degree guardrail protecting Swiggy from a false
# ring also, at large enough scale, excludes this device from Layer 1. That's
# the actual precision/recall trade-off `validate.precision_recall_curve`
# makes visible, not a bug to hide.

_ADVERSARY_DEVICE = "adv-device-rotator-01"


def adversarial_split_reports(n_victims: int = 50, base_time=None, seed: int = 0) -> list[Report]:
    """`n_victims` incidents, each with a UNIQUE payee UPI and phone (no two
    share a hard identifier pairwise) but ALL sharing one `device_hint` --
    a mule-farm device reused at a scale (`n_victims`) meant to exceed a
    realistic `hub_degree_cap`, so the same guardrail that protects a
    legitimate popular payee also excludes this device from Layer 1.

    `n_victims` must therefore stay ABOVE the cap the scenario is described at,
    or there is no tension left to demonstrate: the device survives the cap,
    Layer 1 simply links the victims, and `describe_adversarial_case` reports
    `passed=False` because the limitation it exists to state no longer holds.
    The default tracks `DEMO_HUB_DEGREE_CAP` (40) with room to spare."""
    from src.generate.messages import _report  # reuse the Report-builder, not a new one

    rng = np.random.default_rng(seed)
    base_time = base_time or __import__("pandas").Timestamp("2026-06-01T10:00:00+05:30")
    reports = []
    for i in range(n_victims):
        amount = int(rng.integers(5_000, 20_000))
        reports.append(_report(
            timestamp=base_time + timedelta(minutes=20 * i),
            channel="sms",
            raw_text=(
                f"Your KYC will expire today. Pay Rs.{amount} to adv{i:02d}@okaxis "
                f"or call 900000{i:04d} immediately to avoid account suspension."
            ),
            is_scam=True,
            confidence=0.9,
            scam_type="kyc_update",
            red_flags=["urgency", "payment_demand", "threat"],
            payee_upi=[f"adv{i:02d}@okaxis"],
            phone=[f"900000{i:04d}"],
            amount=amount,
            extraction_confidence=0.9,
            ring_id="RADV",
            is_kingpin_incident=False,
            planted_typology="ring",
        ))
    # device_hint isn't a `_report()` kwarg (messages.py doesn't use it) --
    # stamp it on afterwards via model_copy so every incident shares one device.
    return [r.model_copy(update={"entities": r.entities.model_copy(update={"device_hint": _ADVERSARY_DEVICE})})
            for r in reports]


def describe_adversarial_case(reports: list[Report], hub_degree_cap: int = 8) -> GuardrailResult:
    """Runs the adversarial scenario end to end at the SAME `hub_degree_cap`
    the rest of the demo uses, and reports what actually happened -- honestly.
    Expected (and asserted by the test): with `n_victims > hub_degree_cap`,
    Layer 1 finds no ring (the shared device is excluded by the guardrail,
    exactly as a legitimate hub would be); Layer 2 -- which always re-admits
    hub-capped nodes via `ring_union_graph` -- still surfaces the device as
    the top lead bridging every victim, clearly labelled a lead, not proof."""
    g = build_graph(reports)
    device_node = f"device:{_ADVERSARY_DEVICE}"

    layer1_rings = detect_rings(g, min_incidents=2, hub_degree_cap=hub_degree_cap)
    layer1_caught = any(device_node in r.identifier_nodes for r in layer1_rings)

    # Layer 2 is centrality across `rings`, so it needs ring inputs even when
    # Layer 1 (rightly, per the guardrail) found none worth calling a ring --
    # seed it with each incident as its own singleton starting point.
    # `ring_union_graph` pulls neighbours from the FULL (uncapped) graph, so
    # the shared device is still reachable even though Layer 1 excluded it.
    singleton_rings = [
        Ring(f"S{i:04d}", frozenset({f"incident:{r.report_id}"}), frozenset())
        for i, r in enumerate(reports)
    ]
    scores = rank_kingpins(g, singleton_rings)
    top = scores[0] if scores else None
    layer2_bridged = bool(top and top.node == device_node and len(top.ring_ids) == len(reports))

    passed = (not layer1_caught) and layer2_bridged
    # State the degree comparison as it actually came out. Hard-coding ">" read
    # as a false claim ("degree 12 > hub_degree_cap=40") the moment the cap moved
    # past the scenario's scale -- in a guardrail, whose entire job is to report
    # honestly on itself.
    degree = g.degree(device_node)
    detail = (
        f"{len(reports)} victims, each with a unique payee UPI and phone, sharing one device "
        f"(degree {degree} vs hub_degree_cap={hub_degree_cap}: "
        f"{'excluded as a hub' if degree > hub_degree_cap else 'NOT excluded'}). Layer 1 (hard "
        f"identifiers, guardrail applied): {'found' if layer1_caught else 'did NOT find'} a ring "
        "linking them -- the device is excluded for the same reason a genuine popular hub is, "
        "which Layer 1 states as a limitation rather than silently missing. Layer 2: the shared "
        f"device {'was' if layer2_bridged else 'was NOT'} surfaced as the top cross-incident lead "
        "bridging all victims -- reported as a lead, not asserted as proof."
    )
    return GuardrailResult(name="adversarial_identifier_rotation", passed=passed, detail=detail)
