"""Tests for src/detector/eval_uci.py -- the G2 real-data eval (CLAUDE.md
§15). Runs the rules-floor classifier against the real UCI SMS Spam
Collection to get a false-positive-rate number that isn't circular (the
rest of the corpus is rendered from the same templates the keywords were
tuned on). Skipped when the (gitignored, Kaggle-sourced) CSV hasn't been
downloaded -- see docs/DATASETS.md §2.
"""
from __future__ import annotations

import json

import pytest

from src.detector.eval_uci import DEFAULT_CSV_PATH, evaluate_rules, load_uci_sms

pytestmark = pytest.mark.skipif(
    not DEFAULT_CSV_PATH.exists(),
    reason="UCI SMS CSV not downloaded -- see docs/DATASETS.md §2",
)


def test_load_uci_sms_parses_real_ham_and_spam_counts():
    rows = load_uci_sms()
    labels = [label for label, _ in rows]
    assert set(labels) == {"ham", "spam"}
    assert labels.count("ham") > 4000
    assert labels.count("spam") > 500
    assert len(rows) == len(labels)


def test_evaluate_rules_ham_false_positive_rate_is_low_on_real_text():
    # Measured value on the full corpus: 0/4825 = 0.0% (CLAUDE.md §15 G2;
    # was 6 at first run -- B10 removed the "mummy"/"mom-in-moment" hits,
    # B11 the bare-"loan"/"pay you back" ones). The 1% ceiling is kept (not
    # tightened to 0) so this stays a loud regression alarm for the deck's
    # FP slide number, not a flaky exact-match.
    rows = load_uci_sms()
    result = evaluate_rules(rows)
    assert result.n_ham > 4000
    assert result.n_spam > 500
    assert result.ham_false_positive_rate < 0.01


def test_evaluate_rules_result_is_json_safe_and_internally_consistent():
    rows = load_uci_sms()
    result = evaluate_rules(rows)
    d = result.to_dict()
    json.dumps(d)  # must not raise
    assert d["n_ham"] == result.n_ham
    assert d["ham_false_positive_rate"] == round(result.ham_false_positives / result.n_ham, 4)
    assert d["spam_flagged_rate"] == round(result.spam_flagged / result.n_spam, 4)
