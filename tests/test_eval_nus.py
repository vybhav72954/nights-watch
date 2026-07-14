"""Tests for src/detector/eval_nus.py -- a truly held-out real-data eval.

Unlike UCI (test_eval_uci.py, CLAUDE.md §15 G2), no fix in this repo was ever
made in response to a message from this corpus -- see eval_nus.py's module
docstring. Skipped when the (gitignored) NUS SMS Corpus XML hasn't been
downloaded -- see docs/DATASETS.md §2.
"""
from __future__ import annotations

import json

import pytest

from src.detector.eval_nus import DEFAULT_XML_PATH, evaluate_rules, load_nus_sms

pytestmark = pytest.mark.skipif(
    not DEFAULT_XML_PATH.exists(),
    reason="NUS SMS Corpus XML not downloaded -- see docs/DATASETS.md §2",
)


def test_load_nus_sms_parses_real_messages():
    texts = load_nus_sms()
    assert len(texts) > 50000
    assert all(isinstance(t, str) and t for t in texts)


def test_evaluate_rules_false_positive_rate_is_low_on_real_never_tuned_text():
    # Measured on the full corpus: 4/55,835 = 0.0001 (0.01%) -- CLAUDE.md
    # §15 G7. No keyword change was made in response to this run (that
    # would defeat the point of a held-out corpus); the 0.1% ceiling is
    # generous headroom for a loud regression alarm, not an exact match.
    texts = load_nus_sms()
    result = evaluate_rules(texts)
    assert result.n_messages > 50000
    assert result.false_positive_rate < 0.001


def test_evaluate_rules_result_is_json_safe_and_internally_consistent():
    texts = load_nus_sms()
    result = evaluate_rules(texts)
    d = result.to_dict()
    json.dumps(d)  # must not raise
    assert d["n_messages"] == result.n_messages
    assert d["false_positive_rate"] == round(result.false_positives / result.n_messages, 4)
