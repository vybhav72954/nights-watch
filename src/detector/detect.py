"""The detector entry point: raw text -> a schema-valid `Report`.

Entity extraction is always regex (`entities.py`) -- the graph must not
depend on an LLM being configured. Classification prefers the optional
Groq path (`llm.py`) and falls back to the deterministic rules
(`classify.py`) when it returns `None`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

from src.detector.classify import classify
from src.detector.entities import extract_entities, extraction_confidence
from src.detector.llm import classify_with_llm
from src.schema import Channel, Report


def detect(
    raw_text: str,
    *,
    channel: Channel = "sms",
    timestamp: datetime | None = None,
    language: str = "en",
    use_llm: bool = True,
) -> Report:
    entities = extract_entities(raw_text)

    verdict = classify_with_llm(raw_text) if use_llm else None
    device_hint = None
    if verdict is not None:
        device_hint = verdict.pop("device_hint", None)
    else:
        verdict = classify(raw_text, entities)
    if device_hint:
        entities["device_hint"] = device_hint

    payload = {
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "channel": channel,
        "raw_text": raw_text,
        "language": language,
        "verdict": verdict,
        "entities": entities,
        "extraction_confidence": extraction_confidence(entities),
    }
    try:
        return Report.model_validate(payload)
    except ValidationError:
        # `llm.py` sanitises its output, but an LLM-backed verdict is still
        # untrusted input at this boundary (CLAUDE.md B2) -- if it somehow
        # still fails the contract, don't crash the citizen's report, fall
        # back to the deterministic rules floor instead.
        payload["verdict"] = classify(raw_text, entities)
        return Report.model_validate(payload)
