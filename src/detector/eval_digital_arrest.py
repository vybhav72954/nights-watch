"""Digital-arrest precision/recall on the synthetic answer-key corpus.

The ET final-round rubric scores "digital arrest scam detection precision and
recall" as its own line item (CLAUDE.md §3, row 2). Until now the repo had a
ring-recovery number (P/R 1.0 ± 0.0, G6) and an LLM-vs-rules agreement number
(82/100), but neither is a scam_type classification figure -- this module
produces the missing one.

It pools the exact corpus generator the demo uses (`generate_messages`) across
several seeds into one labelled set -- each ring carries a planted `scam_type`,
each legit message carries `legit` -- runs the deterministic rules-floor
`classify()` over `raw_text`, and computes precision/recall/F1 for the
`digital_arrest` class (plus the binary scam-vs-legit numbers, for context).

Caveat, stated plainly (CLAUDE.md §7 ethics, and the same posture as G6's
ring P/R): the keyword lists in `classify.py` were designed to separate exactly
these templates, so a high number here means the method recovers the PLANTED
answer key -- not that it scores this on real-world digital-arrest text, of
which there is no labelled corpus to measure recall against. That honest gap is
why the real-data number for the citizen tool is the FALSE-POSITIVE rate
(UCI 0/4,825, NUS 4/55,835 -- eval_uci.py / eval_nus.py). Cite all three
together; this figure answers "does the classifier separate the scam it targets
from the other scams and from legit traffic," measured, not asserted (§17).
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from src.detector.classify import classify
from src.generate.messages import generate_messages

DIGITAL_ARREST = "digital_arrest"
DEFAULT_SEEDS = tuple(range(20))


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


@dataclass(frozen=True)
class DigitalArrestEvalResult:
    seeds: tuple[int, ...]
    n_messages: int
    # digital_arrest as the positive class (multi-class scam_type problem):
    support: int          # planted digital_arrest messages
    true_positives: int
    false_positives: int  # a non-digital_arrest message predicted digital_arrest
    false_negatives: int  # a planted digital_arrest message predicted otherwise
    # binary scam-vs-legit (context, not the headline):
    n_scam: int
    n_legit: int
    scam_true_positives: int
    scam_false_positives: int  # a legit message flagged as a scam

    @property
    def precision(self) -> float:
        return _prf(self.true_positives, self.false_positives, self.false_negatives)[0]

    @property
    def recall(self) -> float:
        return _prf(self.true_positives, self.false_positives, self.false_negatives)[1]

    @property
    def f1(self) -> float:
        return _prf(self.true_positives, self.false_positives, self.false_negatives)[2]

    @property
    def scam_precision(self) -> float:
        return _prf(self.scam_true_positives, self.scam_false_positives,
                    self.n_scam - self.scam_true_positives)[0]

    @property
    def scam_recall(self) -> float:
        return _prf(self.scam_true_positives, self.scam_false_positives,
                    self.n_scam - self.scam_true_positives)[1]

    def to_dict(self) -> dict:
        return {
            "seeds": list(self.seeds),
            "n_messages": self.n_messages,
            "digital_arrest": {
                "support": self.support,
                "true_positives": self.true_positives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
                "precision": self.precision,
                "recall": self.recall,
                "f1": self.f1,
            },
            "scam_vs_legit": {
                "n_scam": self.n_scam,
                "n_legit": self.n_legit,
                "false_positives_on_legit": self.scam_false_positives,
                "precision": self.scam_precision,
                "recall": self.scam_recall,
            },
        }


def build_labeled_corpus(seeds=DEFAULT_SEEDS) -> list[tuple[str, bool, str]]:
    """Pools `generate_messages` across `seeds` into (planted_scam_type,
    planted_is_scam, raw_text) triples. Pooling matters: a single 6-ring seed
    draws each ring's scam_type at random, so ~40% of seeds contain no
    digital_arrest ring at all -- pooling 20 seeds gives stable class support."""
    corpus: list[tuple[str, bool, str]] = []
    for seed in seeds:
        for report in generate_messages(seed=seed):
            corpus.append((report.verdict.scam_type, report.verdict.is_scam, report.raw_text))
    return corpus


def evaluate_rules(corpus: list[tuple[str, bool, str]], seeds=DEFAULT_SEEDS) -> DigitalArrestEvalResult:
    """Runs the deterministic rules-floor `classify()` (no API key needed --
    the B1/B3-safe path, same as eval_uci/eval_nus) and counts digital_arrest
    TP/FP/FN plus the binary scam/legit tallies."""
    tp = fp = fn = 0
    n_scam = n_legit = scam_tp = scam_fp = 0
    for planted_type, planted_scam, text in corpus:
        pred = classify(text)
        pred_type = pred["scam_type"]
        pred_scam = pred["is_scam"]

        planted_da = planted_type == DIGITAL_ARREST
        pred_da = pred_type == DIGITAL_ARREST
        tp += planted_da and pred_da
        fp += (not planted_da) and pred_da
        fn += planted_da and (not pred_da)

        if planted_scam:
            n_scam += 1
            scam_tp += pred_scam
        else:
            n_legit += 1
            scam_fp += pred_scam

    return DigitalArrestEvalResult(
        seeds=tuple(seeds),
        n_messages=len(corpus),
        support=tp + fn,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        n_scam=n_scam,
        n_legit=n_legit,
        scam_true_positives=scam_tp,
        scam_false_positives=scam_fp,
    )


def sample_llm_comparison(
    corpus: list[tuple[str, bool, str]],
    *,
    n_per_class: int = 40,
    seed: int = 0,
    model: str = "llama-3.3-70b-versatile",
) -> dict | None:
    """Runs a BALANCED sample of the corpus through the LLM path (the demo's
    primary classifier) and measures ITS digital_arrest precision/recall against
    the same planted labels, plus the rules-vs-LLM agreement on is_scam.

    This is the LLM as the classifier being scored, NOT an LLM judge: the
    labels are planted (correct by construction), so there is nothing for a
    judge to adjudicate -- a judge could only add noise to a known-correct
    label. What is genuinely uncertain, and what this measures, is whether the
    *LLM classifier* also recovers those labels on the same text.

    Returns None (never raises) the moment the LLM path can't produce a verdict
    -- no API key, no groq, an API failure -- the same degrade-cleanly contract
    as classify_with_llm and eval_uci.sample_llm_comparison, so a keyless
    machine skips it rather than reporting a partial number.

    Balanced by design: digital_arrest is ~4% of the pooled corpus, so a random
    100-row sample holds only ~4 positives -- too few for a recall number. This
    samples up to n_per_class planted-DA and n_per_class non-DA messages
    explicitly."""
    from src.detector.llm import classify_with_llm

    rng = random.Random(seed)
    positives = [row for row in corpus if row[0] == DIGITAL_ARREST]
    negatives = [row for row in corpus if row[0] != DIGITAL_ARREST]
    sample = (
        rng.sample(positives, min(n_per_class, len(positives)))
        + rng.sample(negatives, min(n_per_class, len(negatives)))
    )

    tp = fp = fn = 0
    agree = checked = 0
    for planted_type, _planted_scam, text in sample:
        llm = classify_with_llm(text, model=model)
        if llm is None:
            return None
        planted_da = planted_type == DIGITAL_ARREST
        llm_da = llm["scam_type"] == DIGITAL_ARREST
        tp += planted_da and llm_da
        fp += (not planted_da) and llm_da
        fn += planted_da and (not llm_da)
        agree += classify(text)["is_scam"] == llm["is_scam"]
        checked += 1

    precision, recall, f1 = _prf(tp, fp, fn)
    return {
        "n": checked,
        "model": model,
        "digital_arrest": {
            "support": tp + fn,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "rules_llm_agreement_rate": round(agree / checked, 4) if checked else 0.0,
    }


def main() -> None:
    corpus = build_labeled_corpus()
    result = evaluate_rules(corpus)
    out = result.to_dict()

    # LLM path comparison is included only when a key is actually configured;
    # on a keyless machine it degrades to None and the artifact carries the
    # rules-floor number alone (the reproducible, §17-safe figure).
    llm_sample = sample_llm_comparison(corpus)
    if llm_sample:
        out["llm_sample"] = llm_sample

    print(json.dumps(out, indent=2))

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "digital_arrest_eval.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
