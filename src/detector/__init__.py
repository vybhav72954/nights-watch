from __future__ import annotations

from src.detector.classify import classify
from src.detector.detect import detect
from src.detector.entities import (
    EntitySpan,
    entity_spans,
    extract_entities,
    extraction_confidence,
)
from src.detector.eval_uci import UciEvalResult, evaluate_rules, load_uci_sms
from src.detector.guidance import guidance
from src.detector.llm import active_classifier_path, classify_with_llm
from src.detector.red_flags import detect_red_flags

__all__ = [
    "active_classifier_path",
    "classify",
    "classify_with_llm",
    "detect",
    "detect_red_flags",
    "EntitySpan",
    "entity_spans",
    "extract_entities",
    "extraction_confidence",
    "guidance",
    "UciEvalResult",
    "evaluate_rules",
    "load_uci_sms",
]
