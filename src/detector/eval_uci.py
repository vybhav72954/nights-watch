"""UCI SMS Spam Collection real-data eval (CLAUDE.md §15 G2).

Every quantitative claim in the deck must be produced by code (CLAUDE.md
§17), and until now the detector was only ever validated against messages
rendered from the same templates its own keywords were tuned on -- a
circular check. This runs the rules-floor `classify()` over ~5,572 real,
human-labelled UK SMS (ham/spam, `docs/DATASETS.md` §2) to get an honest
number for the citizen-tool false-positive-rate criterion (CLAUDE.md §3).

Caveat, stated plainly (CLAUDE.md §7 ethics): UCI "spam" is commercial /
premium-rate marketing spam, not Indian digital-arrest / parcel / KYC scam
text -- `spam_flagged_rate` is NOT a scam_type recall benchmark, and a low
number there does not mean the detector is weak on the scams it targets
(see `src/generate/templates.py` for those). What this eval DOES honestly
measure is `ham_false_positive_rate`: how often real, ordinary text gets
wrongly told "this is a scam", using messages the keyword list was never
tuned against.
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path

from src.detector.classify import classify

DEFAULT_CSV_PATH = Path("data/raw/sms/spam.csv")


@dataclass(frozen=True)
class UciEvalResult:
    n_ham: int
    n_spam: int
    ham_false_positives: int
    spam_flagged: int

    @property
    def ham_false_positive_rate(self) -> float:
        return round(self.ham_false_positives / self.n_ham, 4) if self.n_ham else 0.0

    @property
    def spam_flagged_rate(self) -> float:
        return round(self.spam_flagged / self.n_spam, 4) if self.n_spam else 0.0

    def to_dict(self) -> dict:
        return {
            "n_ham": self.n_ham,
            "n_spam": self.n_spam,
            "ham_false_positives": self.ham_false_positives,
            "ham_false_positive_rate": self.ham_false_positive_rate,
            "spam_flagged": self.spam_flagged,
            "spam_flagged_rate": self.spam_flagged_rate,
        }


def load_uci_sms(csv_path: Path = DEFAULT_CSV_PATH) -> list[tuple[str, str]]:
    """Returns (label, text) pairs, label in {"ham", "spam"}. The Kaggle
    mirror ships as `v1,v2,...` with latin-1 encoding and three empty
    trailing columns -- see docs/DATASETS.md §2 for the acquisition command."""
    rows: list[tuple[str, str]] = []
    with open(csv_path, encoding="latin-1", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header: v1,v2,Unnamed: 2,Unnamed: 3,Unnamed: 4
        for row in reader:
            if len(row) < 2 or not row[0]:
                continue
            label, text = row[0].strip(), row[1]
            if label in ("ham", "spam") and text:
                rows.append((label, text))
    return rows


def evaluate_rules(rows: list[tuple[str, str]]) -> UciEvalResult:
    """Runs the deterministic rules-floor `classify()` (no API key needed --
    this is the path that must stay safe with no LLM configured, B1/B3)."""
    n_ham = n_spam = ham_fp = spam_flagged = 0
    for label, text in rows:
        is_scam = classify(text)["is_scam"]
        if label == "ham":
            n_ham += 1
            ham_fp += is_scam
        else:
            n_spam += 1
            spam_flagged += is_scam
    return UciEvalResult(n_ham, n_spam, ham_fp, spam_flagged)


def sample_llm_comparison(rows: list[tuple[str, str]], *, n: int = 100, seed: int = 0) -> dict | None:
    """Runs `n` random rows through the LLM path for a rules-vs-LLM spot
    check. Returns `None` (never raises) if no API key is configured -- the
    same degrade-cleanly contract as `classify_with_llm` itself, so callers
    can skip the comparison rather than report a partial number."""
    from src.detector.llm import classify_with_llm

    sample = random.Random(seed).sample(rows, min(n, len(rows)))
    agree = checked = 0
    for _label, text in sample:
        llm_verdict = classify_with_llm(text)
        if llm_verdict is None:
            return None
        rules_is_scam = classify(text)["is_scam"]
        checked += 1
        agree += rules_is_scam == llm_verdict["is_scam"]
    return {"n": checked, "rules_llm_agreement_rate": round(agree / checked, 4) if checked else 0.0}


def main() -> None:
    rows = load_uci_sms()
    result = evaluate_rules(rows)
    print(json.dumps(result.to_dict(), indent=2))

    llm_comparison = sample_llm_comparison(rows)
    if llm_comparison:
        print(json.dumps(llm_comparison, indent=2))

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "uci_eval.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
