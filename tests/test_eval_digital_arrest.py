"""Tests for src/detector/eval_digital_arrest.py -- the digital-arrest P/R eval.

Unlike the UCI/NUS evals this one needs no external download: it generates its
own labelled answer-key corpus (`generate_messages`), so it always runs. The
number it guards is the ET rubric's row-2 criterion (CLAUDE.md §3): digital
arrest scam detection precision and recall, measured on the synthetic corpus
with the caveat stated in the module docstring (recovers the planted answer key,
not a real-world claim -- that's the FP-rate evals' job).
"""
from __future__ import annotations

import json

from src.detector.eval_digital_arrest import (
    DEFAULT_SEEDS,
    build_labeled_corpus,
    evaluate_rules,
    sample_llm_comparison,
)


def test_corpus_pools_seeds_with_meaningful_digital_arrest_support():
    corpus = build_labeled_corpus()
    assert len(corpus) > 1000
    planted_da = sum(1 for t, _scam, _text in corpus if t == "digital_arrest")
    # ~40% of single seeds draw no digital_arrest ring at all, which is why the
    # eval pools -- pooled support must be large enough for a stable P/R.
    assert planted_da >= 40
    # every planted digital_arrest message is a scam; every legit is not.
    assert all(scam for t, scam, _ in corpus if t == "digital_arrest")
    assert all(not scam for t, scam, _ in corpus if t == "legit")


def test_digital_arrest_precision_and_recall_are_high_on_the_answer_key():
    # Measured, pooled over 20 seeds: precision 1.0, recall 1.0, F1 1.0 on 56
    # planted digital_arrest messages (0 FP, 0 FN). The floors are generous
    # regression alarms, not flaky exact-match -- see the sibling evals'
    # convention. The perfect number carries the synthetic caveat in the
    # module docstring; it is not a real-world digital-arrest recall claim.
    result = evaluate_rules(build_labeled_corpus())
    assert result.support >= 40
    assert result.precision >= 0.9
    assert result.recall >= 0.9
    assert result.f1 >= 0.9
    # no legit message is flagged as a scam on the rules floor (the citizen-tool
    # FP story, here on the synthetic corpus -- UCI/NUS carry the real-data one).
    assert result.scam_false_positives == 0


def test_llm_comparison_degrades_to_none_without_a_key():
    # conftest.py strips GROQ_API_KEY per-test, so classify_with_llm returns
    # None on the first call and sample_llm_comparison bails cleanly -- the
    # same degrade contract as eval_uci. A keyed run (python -m
    # src.detector.eval_digital_arrest) is the only place this returns numbers,
    # which is why the LLM figure is not a suite-guarded (network-free) number.
    assert sample_llm_comparison(build_labeled_corpus()) is None


def test_result_is_json_safe_and_internally_consistent():
    result = evaluate_rules(build_labeled_corpus())
    d = result.to_dict()
    json.dumps(d)  # must not raise
    da = d["digital_arrest"]
    assert da["true_positives"] + da["false_negatives"] == da["support"]
    assert da["support"] == result.support
    assert d["seeds"] == list(DEFAULT_SEEDS)
    assert d["scam_vs_legit"]["n_scam"] + d["scam_vs_legit"]["n_legit"] == d["n_messages"]
