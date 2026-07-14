"""Layer 2: the kingpin lead pack. Wraps `KingpinScore` (`src/graph/kingpin.py`)
with a narrative and an explicit, unmissable disclaimer -- CLAUDE.md is
emphatic that this is a prioritisation signal, never evidence, and the object
model here is built so a caller can't accidentally present it as a `Ring`'s
evidence pack (`pack.py`) is presented: no `to_pdf`/`to_json` "proof" export,
`label` is hard-coded, and the disclaimer ships with every instance.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.graph.kingpin import KingpinScore
from src.graph.rings import Ring

DISCLAIMER = (
    "This is an investigative LEAD based on network centrality across rings, "
    "NOT legal proof. It must be corroborated with independent evidence "
    "(e.g. financial records, a Layer-1 evidence pack per ring) before any action."
)


@dataclass(frozen=True)
class KingpinLead:
    node: str
    kind: str
    score: float
    bridged_ring_ids: tuple[str, ...]
    bridged_incident_count: int
    narrative: str
    label: str = "lead"
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "layer": 2,
            "label": self.label,
            "node": self.node,
            "kind": self.kind,
            "score": self.score,
            "bridged_ring_ids": list(self.bridged_ring_ids),
            "bridged_incident_count": self.bridged_incident_count,
            "narrative": self.narrative,
            "disclaimer": self.disclaimer,
        }


def _narrative(score: KingpinScore) -> str:
    value = score.node.split(":", 1)[1]
    if len(score.ring_ids) <= 1:
        return (
            f"{score.kind} `{value}` ranks highly by centrality but touches at most one "
            "detected ring -- not currently a cross-ring bridge."
        )
    rings = ", ".join(sorted(score.ring_ids))
    return (
        f"{score.kind} `{value}` is central across {len(score.ring_ids)} otherwise-separate "
        f"rings ({rings}) — the kind of shared infrastructure a ring coordinator, not a "
        "single scammer, would reuse."
    )


def build_kingpin_lead(score: KingpinScore, rings: list[Ring]) -> KingpinLead:
    bridged = [r for r in rings if r.ring_id in score.ring_ids]
    incident_count = len({inc for r in bridged for inc in r.incident_ids})
    return KingpinLead(
        node=score.node,
        kind=score.kind,
        score=score.score,
        bridged_ring_ids=tuple(sorted(score.ring_ids)),
        bridged_incident_count=incident_count,
        narrative=_narrative(score),
    )


def build_kingpin_leads(scores: list[KingpinScore], rings: list[Ring], top_k: int = 5) -> list[KingpinLead]:
    return [build_kingpin_lead(s, rings) for s in scores[:top_k]]
