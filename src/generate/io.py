"""JSONL round-trip for `Report` corpora (`data/synthetic/*.jsonl`)."""
from __future__ import annotations

import json
from pathlib import Path

from src.schema import Report


def write_reports_jsonl(reports: list[Report], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for report in reports:
            f.write(json.dumps(report.model_dump(mode="json", by_alias=True)) + "\n")


def read_reports_jsonl(path: str | Path) -> list[Report]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return [Report.model_validate(json.loads(line)) for line in f if line.strip()]


def answer_key(reports: list[Report]) -> dict:
    """JSON-serialisable summary of the planted ground truth, derived from
    each report's `_gt` -- lets Prove validate ring/kingpin recovery without
    re-parsing the whole corpus."""
    rings: dict[str, list[str]] = {}
    kingpin_report_ids: list[str] = []
    for r in reports:
        if r.gt and r.gt.ring_id:
            rings.setdefault(r.gt.ring_id, []).append(r.report_id)
        if r.gt and r.gt.is_kingpin_incident:
            kingpin_report_ids.append(r.report_id)
    return {
        "rings": {rid: {"report_ids": ids, "size": len(ids)} for rid, ids in rings.items()},
        "kingpin_report_ids": kingpin_report_ids,
    }
