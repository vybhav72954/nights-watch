"""NUS SMS Corpus real-data eval -- a truly held-out ham check.

`eval_uci.py` (CLAUDE.md §15 G2) is the UCI SMS Spam Collection eval, and it
carries an honest caveat: the false positives it first found (6/4,825) *drove*
keyword fixes B10/B11, so UCI is now a regression harness for those specific
fixes, not an untouched held-out set (CLAUDE.md §15 G2, §14 B10/B11).

This module runs the same rules-floor `classify()` over the NUS SMS Corpus
(Tao Chen and Min-Yen Kan, 2013 -- 55,835 real SMS collected from Singaporean
students, mostly Singlish/casual English) -- a corpus this detector's keyword
lists have never been tuned against, in either direction. No fix in this repo
was made in response to a message from this corpus. Whatever
`false_positive_rate` comes out is the number to trust for "how does this
generalise to real text nobody hand-picked."

Caveat, stated plainly (CLAUDE.md §7 ethics): the NUS corpus has no
spam/scam label -- it is organic conversational traffic, not a spam
collection -- so it can only measure false positives on ordinary real-world
text, the same "citizen-tool FP rate" criterion UCI's ham fold measures
(CLAUDE.md §3). It cannot produce a scam-recall number (there is nothing to
recall). Source + citation requirement: docs/DATASETS.md §2.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from src.detector.classify import classify

DEFAULT_XML_PATH = Path("data/raw/nus_sms/smsCorpus_en_2015.03.09_all.xml")


@dataclass(frozen=True)
class NusEvalResult:
    n_messages: int
    false_positives: int

    @property
    def false_positive_rate(self) -> float:
        return round(self.false_positives / self.n_messages, 4) if self.n_messages else 0.0

    def to_dict(self) -> dict:
        return {
            "n_messages": self.n_messages,
            "false_positives": self.false_positives,
            "false_positive_rate": self.false_positive_rate,
        }


def load_nus_sms(xml_path: Path = DEFAULT_XML_PATH) -> list[str]:
    """Returns raw message texts from the NUS SMS Corpus XML release. Every
    <message> in the 2015.03.09 English snapshot carries language="en" and a
    <text> child -- see docs/DATASETS.md §2 for the download command."""
    texts: list[str] = []
    root = ET.parse(xml_path).getroot()
    for message in root.iter("message"):
        text_el = message.find("text")
        if text_el is not None and text_el.text and text_el.text.strip():
            texts.append(text_el.text)
    return texts


def evaluate_rules(texts: list[str]) -> NusEvalResult:
    """Runs the deterministic rules-floor `classify()` (no API key needed --
    matches eval_uci.py's evaluate_rules, same B1/B3-safe path)."""
    false_positives = sum(1 for text in texts if classify(text)["is_scam"])
    return NusEvalResult(len(texts), false_positives)


def main() -> None:
    texts = load_nus_sms()
    result = evaluate_rules(texts)
    print(json.dumps(result.to_dict(), indent=2))

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "nus_eval.json").write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
