"""Suite-wide isolation: no test may silently reach the real LLM.

`detect()` defaults to `use_llm=True`, and with the `groq` package installed
a real GROQ_API_KEY in the environment (or the auto-loaded `.env`, B8) would
make every unmocked detect() test fire real network calls -- nondeterministic
verdicts, venue rate limits, and a red suite on exactly the machine where it
matters most, the demo laptop (CLAUDE.md B15). Tests that want the LLM path
install a fake `groq` module and set the key explicitly inside the test body,
which overrides this fixture (see tests/test_detector.py).
"""
import pytest


@pytest.fixture(autouse=True)
def _no_real_llm_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
