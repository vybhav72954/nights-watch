"""Lead-time replay -- the "flagged at report k; N-k more victims would have
followed" counterfactual (CLAUDE.md §15 G1). This is the one judged criterion
(fraud-network detection lead time before mass victimisation) with no code
behind it until now: the rest of the pipeline is batch (`build_graph(all)` ->
`detect_rings`), which can show a ring exists but not *when* it first became
detectable.

Replays reports in timestamp order, re-running Layer 1 detection after each
new report, and records the first step at which each planted ring is
recovered PURELY -- every incident in the detected component traces back to
the same `_gt.ring_id`. Purity matters: without it, an uncapped hub gluing
two unrelated rings into one big component would let one ring's early
detection falsely "credit" the other. O(n^2) (a full rebuild + connected-
components pass per step) -- fine at demo/seeded-corpus scale, not meant for
production volumes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.graph import build_graph, detect_rings
from src.schema import Report


@dataclass(frozen=True)
class LeadTimeReplay:
    ring_id: str
    eventual_size: int
    # `detected_at_report` is k, 1-indexed within THIS ring's own reports
    # (e.g. 2 means "detected the moment the ring's 2nd report arrived") --
    # None if the ring never reaches `min_incidents` purely.
    detected_at_report: int | None
    detected_at_timestamp: datetime | None
    victims_after_flag: int | None  # eventual_size - detected_at_report

    def to_dict(self) -> dict:
        return {
            "ring_id": self.ring_id,
            "eventual_size": self.eventual_size,
            "detected_at_report": self.detected_at_report,
            "detected_at_timestamp": (
                self.detected_at_timestamp.isoformat() if self.detected_at_timestamp else None
            ),
            "victims_after_flag": self.victims_after_flag,
        }


def replay_lead_time(
    reports: list[Report], *, hub_degree_cap: int | None = None, min_incidents: int = 2,
) -> list[LeadTimeReplay]:
    """One `LeadTimeReplay` per planted ring (`_gt.ring_id`), ordered by
    `ring_id`, detected rings first."""
    ordered = sorted(reports, key=lambda r: r.timestamp)

    eventual_size: dict[str, int] = {}
    planted_ring_of: dict[str, str] = {}
    for r in ordered:
        if r.gt and r.gt.ring_id:
            eventual_size[r.gt.ring_id] = eventual_size.get(r.gt.ring_id, 0) + 1
            planted_ring_of[r.report_id] = r.gt.ring_id

    detected: dict[str, LeadTimeReplay] = {}
    seen_so_far: dict[str, int] = {}
    for i, report in enumerate(ordered, start=1):
        if report.report_id in planted_ring_of:
            rid = planted_ring_of[report.report_id]
            seen_so_far[rid] = seen_so_far.get(rid, 0) + 1

        if len(detected) == len(eventual_size):
            break

        g = build_graph(ordered[:i])
        rings = detect_rings(g, min_incidents=min_incidents, hub_degree_cap=hub_degree_cap)
        for ring in rings:
            incident_report_ids = {n.split(":", 1)[1] for n in ring.incident_ids}
            planted_ids = {planted_ring_of.get(rid) for rid in incident_report_ids}
            if len(planted_ids) != 1:
                continue  # impure component -- don't credit any ring with a false-early hit
            rid = next(iter(planted_ids))
            if rid is None or rid in detected:
                continue
            k = seen_so_far[rid]
            detected[rid] = LeadTimeReplay(
                ring_id=rid,
                eventual_size=eventual_size[rid],
                detected_at_report=k,
                detected_at_timestamp=report.timestamp,
                victims_after_flag=eventual_size[rid] - k,
            )

    undetected = [
        LeadTimeReplay(rid, n, None, None, None)
        for rid, n in eventual_size.items() if rid not in detected
    ]
    return sorted(detected.values(), key=lambda lt: lt.ring_id) + sorted(undetected, key=lambda lt: lt.ring_id)


def lead_time_headline(replays: list[LeadTimeReplay]) -> str | None:
    """The single-sentence closer for the deck (CLAUDE.md §17 slide 10) --
    picks the largest-eventual-size DETECTED ring so the claim is produced by
    code, not asserted. `None` if nothing was detected."""
    detected = [r for r in replays if r.detected_at_report is not None]
    if not detected:
        return None
    best = max(detected, key=lambda r: r.eventual_size)
    return (
        f"flagged at report {best.detected_at_report}; "
        f"{best.victims_after_flag} subsequent victims were preventable."
    )
