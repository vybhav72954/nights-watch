"""Layer 1 evidence pack: the auditable, deterministic proof for one flagged
ring (CLAUDE.md §4.3, docs/SOLUTION_DESIGN.md §4).

Everything in here traces back to a `Ring` (connected components over hard
shared identifiers -- `src/graph/rings.py`) and the reports that make it up.
No score, no ML, no threshold beyond the ones already baked into `detect_rings`
-- that's what makes it presentable as evidence rather than a lead (contrast
`src/evidence/lead.py`).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

from src.graph.rings import Ring
from src.schema import Report


def _code_version() -> str:
    """Short git commit hash the pack was generated under, for the
    methodology stamp's provenance claim. Falls back to "unknown" rather than
    raising -- a demo machine or judge's checkout without git history must
    still produce a pack."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, timeout=5, check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


@dataclass(frozen=True)
class IncidentSummary:
    report_id: str
    timestamp: datetime
    channel: str
    scam_type: str
    amount: int | None
    raw_text: str

    @property
    def raw_text_sha256(self) -> str:
        """Binds this summary to the exact bytes of the citizen's original
        text -- so a court can verify the report in the pack hasn't been
        altered post-hoc, without needing the raw_text itself re-typed."""
        return hashlib.sha256(self.raw_text.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp.isoformat(),
            "channel": self.channel,
            "scam_type": self.scam_type,
            "amount": self.amount,
            "raw_text": self.raw_text,
            "raw_text_sha256": self.raw_text_sha256,
        }


@dataclass(frozen=True)
class SharedIdentifier:
    kind: str
    value: str
    report_ids: frozenset[str]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value, "report_ids": sorted(self.report_ids)}


@dataclass(frozen=True)
class EvidencePack:
    ring_id: str
    generated_at: datetime
    incidents: tuple[IncidentSummary, ...]
    shared_identifiers: tuple[SharedIdentifier, ...]
    narrative: str
    methodology: dict

    @property
    def content_sha256(self) -> str:
        """SHA-256 over everything that determines this pack's *content* --
        deliberately excludes `generated_at`, so re-running `build_evidence_pack`
        on the same report set reproduces the identical hash. That's what backs
        the methodology's "regenerable byte-identically" claim: this isn't a
        stored field that could drift from the data, it's derived fresh each
        time from `incidents`/`shared_identifiers`."""
        canonical = {
            "ring_id": self.ring_id,
            "incidents": sorted(
                (i.report_id, i.timestamp.isoformat(), i.channel, i.scam_type, i.amount, i.raw_text_sha256)
                for i in self.incidents
            ),
            "shared_identifiers": sorted(
                (s.kind, s.value, sorted(s.report_ids)) for s in self.shared_identifiers
            ),
        }
        blob = json.dumps(canonical, sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    @property
    def certificate(self) -> dict:
        """Placeholder certification block in Section 63 Bharatiya Sakshya
        Adhiniyam 2023 (the successor to Indian Evidence Act 1872 §65B)
        vocabulary for electronic-record admissibility. This is NOT a signed
        certificate -- it flags exactly what a production deployment would
        need a device custodian to sign, using the right statutory hook for
        an Indian law-enforcement audience."""
        return {
            "statute": "Bharatiya Sakshya Adhiniyam 2023, Section 63 (electronic record)",
            "predecessor": "Indian Evidence Act 1872, Section 65B (superseded)",
            "content_sha256": self.content_sha256,
            "status": "PLACEHOLDER: requires a signed certificate from the person "
                       "in charge of the device/system, per Section 63, before use "
                       "in proceedings; not executed in this demo build",
        }

    def to_dict(self) -> dict:
        return {
            "ring_id": self.ring_id,
            "generated_at": self.generated_at.isoformat(),
            "layer": 1,
            "label": "proof",
            "narrative": self.narrative,
            "incidents": [i.to_dict() for i in self.incidents],
            "shared_identifiers": [s.to_dict() for s in self.shared_identifiers],
            "content_sha256": self.content_sha256,
            "methodology": self.methodology,
            "certificate": self.certificate,
        }

    def to_json(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def to_markdown(self) -> str:
        lines = [
            f"# Evidence Pack: Ring {self.ring_id}",
            f"_Generated {self.generated_at.isoformat()} · Layer 1 (deterministic proof)_",
            "",
            self.narrative,
            "",
            f"## Incidents ({len(self.incidents)})",
        ]
        for inc in sorted(self.incidents, key=lambda i: i.timestamp):
            lines.append(
                f"- `{inc.report_id}` · {inc.timestamp.isoformat()} · {inc.channel} · "
                f"{inc.scam_type} · Rs.{inc.amount if inc.amount is not None else '?'}\n"
                f"  > {inc.raw_text}\n"
                f"  SHA-256: `{inc.raw_text_sha256}`"
            )
        lines.append("")
        lines.append(f"## Shared identifiers ({len(self.shared_identifiers)})")
        for sid in sorted(self.shared_identifiers, key=lambda s: -len(s.report_ids)):
            lines.append(f"- **{sid.kind}** `{sid.value}`: used in {len(sid.report_ids)} incidents")
        lines.append("")
        lines.append("## Methodology")
        for key, value in self.methodology.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")
        lines.append("## Certificate")
        lines.append(f"- Pack content SHA-256: `{self.content_sha256}`")
        for key, value in self.certificate.items():
            if key != "content_sha256":
                lines.append(f"- **{key}**: {value}")
        return "\n".join(lines)

    def to_pdf(self, path: str | Path) -> None:
        """Optional -- requires `reportlab`. Renders the same content as
        `to_markdown()` as a simple, printable document (FIR annexure /
        bank freeze request format)."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate
        except ImportError as e:
            raise ImportError(
                "to_pdf() requires the optional 'reportlab' dependency (pip install reportlab)"
            ) from e

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        SimpleDocTemplate(str(p), pagesize=A4).build(self._pdf_story())

    def _pdf_story(self) -> list:
        """The PDF's flowables -- split from `to_pdf` so tests can assert the
        rendered content (hashes, certificate) without parsing a compressed
        PDF byte stream."""
        from xml.sax.saxutils import escape

        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, Spacer

        styles = getSampleStyleSheet()
        story = [
            Paragraph(f"Evidence Pack: Ring {self.ring_id}", styles["Title"]),
            Paragraph(
                f"Generated {self.generated_at.isoformat()} · Layer 1 (deterministic proof)",
                styles["Normal"],
            ),
            Spacer(1, 12),
            # Paragraph interprets mini-XML markup: tag-like text in an
            # identifier value crashes the build (unclosed tag) or -- worse
            # for a court-facing document -- silently renders as formatting.
            # The narrative is the one story string embedding identifier
            # values, and device_hint is an LLM-supplied free string; escape
            # so untrusted values always render literally (CLAUDE.md B14).
            Paragraph(escape(self.narrative), styles["BodyText"]),
            Spacer(1, 12),
            Paragraph(f"Incidents ({len(self.incidents)})", styles["Heading2"]),
        ]
        incident_rows = [["Report ID", "Timestamp", "Channel", "Scam type", "Amount (Rs.)"]]
        for inc in sorted(self.incidents, key=lambda i: i.timestamp):
            incident_rows.append([
                inc.report_id[:8], inc.timestamp.isoformat(), inc.channel,
                inc.scam_type, str(inc.amount) if inc.amount is not None else "?",
            ])
        story.append(_styled_table(incident_rows))
        story.append(Spacer(1, 6))
        # Hashes don't fit the table's column widths; full-width paragraphs
        # do -- previously omitted entirely, which undercut the integrity
        # story in the one format meant for print (CLAUDE.md §15 G3).
        story.append(Paragraph("Per-incident integrity (SHA-256 of raw text)", styles["Heading3"]))
        for inc in sorted(self.incidents, key=lambda i: i.timestamp):
            story.append(Paragraph(
                f'<b>{inc.report_id[:8]}</b>: <font face="Courier" size="7">{inc.raw_text_sha256}</font>',
                styles["Normal"],
            ))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Shared identifiers ({len(self.shared_identifiers)})", styles["Heading2"]))
        id_rows = [["Kind", "Value", "Used in # incidents"]]
        for sid in sorted(self.shared_identifiers, key=lambda s: -len(s.report_ids)):
            id_rows.append([sid.kind, sid.value, str(len(sid.report_ids))])
        story.append(_styled_table(id_rows))

        story.append(Spacer(1, 12))
        story.append(Paragraph("Methodology", styles["Heading2"]))
        for key, value in self.methodology.items():
            story.append(Paragraph(f"<b>{key}</b>: {value}", styles["Normal"]))

        story.append(Spacer(1, 12))
        story.append(Paragraph("Certificate", styles["Heading2"]))
        story.append(Paragraph(f"<b>Pack content SHA-256</b>: {self.content_sha256}", styles["Normal"]))
        for key, value in self.certificate.items():
            if key != "content_sha256":
                story.append(Paragraph(f"<b>{key}</b>: {value}", styles["Normal"]))
        return story


def _styled_table(rows: list[list[str]]):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    t = Table(rows, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    return t


def _narrative(
    ring: Ring, incidents: list[IncidentSummary], shared: list[SharedIdentifier],
    incident_noun: str = "citizen reports",
) -> str:
    span = ""
    if incidents:
        lo = min(i.timestamp for i in incidents)
        hi = max(i.timestamp for i in incidents)
        span = f" filed between {lo.isoformat()} and {hi.isoformat()}"
    top = sorted(shared, key=lambda s: -len(s.report_ids))[:3]
    id_desc = "; ".join(f"{s.kind} `{s.value}` ({len(s.report_ids)} incidents)" for s in top)
    return (
        f"Ring {ring.ring_id} comprises {len(incidents)} {incident_noun}{span}. "
        f"They are linked by shared hard identifiers, most notably: {id_desc}. "
        "This clustering is a deterministic connected-component computation over "
        "shared identifiers (Layer 1), not a statistical or learned inference, "
        "and is presented as evidence, not a probabilistic lead."
    )


def build_evidence_pack(
    ring: Ring, g: nx.Graph, reports_by_id: dict[str, Report],
    *, incident_noun: str = "citizen reports",
) -> EvidencePack:
    """The detection parameters stamped into the methodology block are read off
    the `Ring` itself, never from the caller: they must be the ones the
    `detect_rings()` call that produced this ring actually used, and a court
    document that misstates how the evidence was derived is worse than one that
    omits it. (They used to be kwargs defaulting to `detect_rings`' defaults --
    so any caller who forgot them silently certified "hub_degree_cap: null" for
    a ring found at 40.)"""
    incidents = []
    for inc_node in ring.incident_ids:
        report_id = g.nodes[inc_node]["report_id"]
        report = reports_by_id[report_id]
        incidents.append(IncidentSummary(
            report_id=report_id,
            timestamp=report.timestamp,
            channel=report.channel,
            scam_type=report.verdict.scam_type,
            amount=report.entities.amount,
            raw_text=report.raw_text,
        ))

    shared = []
    for id_node in ring.identifier_nodes:
        kind = g.nodes[id_node]["kind"]
        value = id_node.split(":", 1)[1]
        touching = frozenset(g.nodes[nb]["report_id"] for nb in g.neighbors(id_node) if nb in ring.incident_ids)
        # A *shared* identifier is one that actually links two of the ring's
        # incidents. An identifier only one incident names -- a live report's
        # own phone number, say -- forms no edge and links nobody to anybody,
        # so itemising it as a shared connection overstates the proof in the
        # one document that must not (CLAUDE.md §3: the pack itemises every
        # shared connection). It stays a node of the ring, just not evidence
        # of linkage. Never empties the list: a component of >= 2 incidents can
        # only be connected through an identifier at least two of them share.
        if len(touching) >= 2:
            shared.append(SharedIdentifier(kind=kind, value=value, report_ids=touching))

    methodology = {
        "algorithm": "deterministic connected components over shared hard "
                      "identifiers (Layer 1): no ML, no statistical inference",
        "parameters": {"hub_degree_cap": ring.hub_degree_cap,
                       "min_incidents": ring.min_incidents},
        "code_version": _code_version(),
        "regenerable": "byte-identical content_sha256 from the same input set "
                        "and parameters (see EvidencePack.content_sha256)",
    }
    return EvidencePack(
        ring_id=ring.ring_id,
        generated_at=datetime.now(timezone.utc),
        incidents=tuple(incidents),
        shared_identifiers=tuple(shared),
        narrative=_narrative(ring, incidents, shared, incident_noun),
        methodology=methodology,
    )
