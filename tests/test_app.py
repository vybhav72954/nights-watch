"""End-to-end tests for the demo app (`app/`) -- headless, offline, deterministic.

Why this file exists: `app/` is the artifact the judges actually see, and it had
**no test in the repo**. Every app bug in CLAUDE.md §16.2-§16.5 (the replay page
accusing the legit hub, the Command centre crashing on any message that linked
to nothing, the hero screen crediting Swiggy with a Layer 1 link) was found by
hand and left with no regression guard, while a green 202-test suite said the
project was fine. These checks are the guard.

They run on the RULES FLOOR -- no API key, no network, which is also the
configuration the app must survive on stage (CLAUDE.md §16). See `_classifier_path`
for why that isn't left to `conftest.py`.

The live-Groq path is the same checks, opted into with a keyed environment:

    NIGHTSWATCH_APP_LLM=1 python -m pytest tests/test_app.py

Run it before any demo freeze. It is what pins the hero message reading as
`digital_arrest` on BOTH paths (A4) -- otherwise the verdict card silently
rewords itself if the venue network drops mid-demo.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APP = _REPO_ROOT / "app" / "streamlit_app.py"
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "app")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Imported at module scope on purpose: importing `src.detector` runs load_dotenv()
# (B8), which repopulates GROQ_API_KEY from `.env`. Doing it HERE, before
# `_rules_floor` strips the key, is what makes the strip stick -- `llm.py` reads
# the key at call time. Popping first and importing later is the A6 bug: the
# import silently puts the key back and the "rules floor" run is really the LLM.
import src.detector as detector  # noqa: E402

HERO_PILL = "⚖️ A digital-arrest scam (demo)"
DECOY_PILL = "✅ A normal message"

# A plausible pasted scam that names the popular merchant alongside the mule.
# Layer 1 excludes the hub, so the screen must not credit it with the link (B21).
HUB_AND_MULE = (
    "CBI arrest warrant. Your swiggy@ybl order is under investigation. "
    "Transfer Rs 50,000 to mule00@okaxis immediately. Call +919876543210."
)
# Names two known mules: one report that bridges two rings we tracked separately.
TWO_MULES = (
    "CBI arrest warrant. Transfer Rs 50,000 to mule00@okaxis and the balance "
    "to mule01@okaxis immediately or a warrant will be issued."
)


LLM_MODE = os.environ.get("NIGHTSWATCH_APP_LLM") == "1"
PATH_UNDER_TEST = "llm" if LLM_MODE else "rules"
# Captured at import, which is after `import src.detector` ran load_dotenv() and
# before any fixture strips the key.
_KEY = os.environ.get("GROQ_API_KEY")


@pytest.fixture(autouse=True)
def _keep_the_key_in_llm_mode(monkeypatch):
    """`conftest.py` strips GROQ_API_KEY before every test body (B15). In LLM mode
    that defeats the point, and silently: the module-scoped `AppTest` fixtures are
    set up first and boot WITH the key, so the checks would pass against the LLM
    while the path assertion read "rules". Same-scope autouse fixtures declared in
    conftest are set up before a module's, so putting the key back here wins."""
    if LLM_MODE and _KEY:
        monkeypatch.setenv("GROQ_API_KEY", _KEY)


@pytest.fixture(scope="module", autouse=True)
def _classifier_path():
    """Pin the classifier path for the whole module.

    Not left to `conftest.py`: its key-strip is function-scoped, and pytest sets
    higher-scoped fixtures up FIRST -- so the module-scoped `AppTest` fixtures
    below boot the app before any function-scoped fixture runs. Stripping the key
    here is therefore the only strip that reaches them. Get this wrong and you
    get A6 exactly: a harness that reports "rules floor" while running the LLM,
    so the offline claim is never actually exercised.
    """
    if LLM_MODE:
        if not os.environ.get("GROQ_API_KEY"):
            pytest.skip("NIGHTSWATCH_APP_LLM=1 but no GROQ_API_KEY (is .env present?)")
        yield
        return
    saved = os.environ.pop("GROQ_API_KEY", None)
    yield
    if saved is not None:
        os.environ["GROQ_API_KEY"] = saved


def _run(*, pill: str | None = None, typed: str | None = None) -> AppTest:
    at = AppTest.from_file(str(_APP), default_timeout=180).run()
    if pill is not None:
        at.get("button_group")[0].set_value(pill).run()
    if typed is not None:
        at.chat_input[0].set_value(typed).run()
    return at


def _html(at: AppTest) -> str:
    return "\n".join(h.proto.body for h in at.get("html"))


def _metrics(at: AppTest) -> dict:
    return {m.label: m for m in at.metric}


@pytest.fixture(scope="module")
def at_idle() -> AppTest:
    return _run()


@pytest.fixture(scope="module")
def at_hero() -> AppTest:
    return _run(pill=HERO_PILL)


@pytest.fixture(scope="module")
def at_decoy() -> AppTest:
    return _run(pill=DECOY_PILL)


@pytest.fixture(scope="module")
def at_hub_and_mule() -> AppTest:
    return _run(typed=HUB_AND_MULE)


@pytest.fixture(scope="module")
def at_two_mules() -> AppTest:
    return _run(typed=TWO_MULES)


# ── the harness must not lie about which path it is testing (A6) ──────────────

def test_the_app_tests_really_run_on_the_declared_path():
    assert detector.active_classifier_path() == PATH_UNDER_TEST


# ── Live page, idle ──────────────────────────────────────────────────────────

def test_live_page_boots_clean(at_idle):
    assert not at_idle.exception


def test_live_page_renders_the_phone_and_the_network_side_by_side(at_idle):
    blob = _html(at_idle)
    assert "wa-phone" in blob and "wa-header" in blob and "wa-body" in blob
    assert len(at_idle.get("iframe")) == 1  # the live network embed
    assert "Nothing is tapped" in blob  # consent-first copy
    assert len(at_idle.chat_input) == 1
    assert len(at_idle.get("button_group")[0].options) == 2  # hero + decoy pills


# ── Beats 1-3: the hero message ──────────────────────────────────────────────

def test_hero_is_classified_and_its_identifiers_are_highlighted_in_the_bubble(at_hero):
    assert not at_hero.exception
    blob = _html(at_hero)
    assert "wa-fwd" in blob and "Forwarded many times" in blob
    assert "Scam detected" in blob
    # scam_type must read the same on BOTH classifier paths or the verdict card
    # silently rewords itself if the venue network drops mid-demo (A4)
    assert "digital arrest" in blob.lower()
    assert "wa-flag" in blob and "wa-advice" in blob
    for value in ("mule00@okaxis", "919999900000", "50,000"):
        assert value in blob


def test_hero_joins_the_seeded_ring_and_says_why(at_hero):
    blob = _html(at_hero)
    assert "wa-hit" in blob and "R0000" in blob

    m = _metrics(at_hero)
    assert m["Incidents in this ring"].value == "31"  # the seeded 30, plus this one
    assert m["Incidents in this ring"].delta == "+1"
    assert "Reported loss in this ring" in m
    assert m["Shared hard identifiers"].value == "1"

    md = "\n".join(x.value for x in at_hero.markdown)
    assert "Why it linked" in md and "mule00@okaxis" in md
    assert any("Linked to known ring" in e.value for e in at_hero.error)
    assert any("not proof" in w.value for w in at_hero.warning)  # Layer 2 tease


def test_the_kingpin_is_the_phone_in_the_heros_own_message_and_is_never_a_layer_1_link():
    """The Layer 2 payoff, and the sharpest question a judge can ask.

    The hero's phone IS the kingpin's: the same number the seeded victims of
    R0000, R0001 and R0002 were called from. So the lead names a number the judge
    just read on screen, instead of one appearing nowhere. But its degree (54) is
    far above the hub cap, so Layer 1 refuses to link on it -- exactly as it
    refuses `swiggy@ybl` -- and "Why it linked" must name the mule UPI ONLY.
    Layer 1 must never be seen using the very node it excluded.
    """
    at = _run(pill=HERO_PILL)
    assert not at.exception

    md = "\n".join(x.value for x in at.markdown)
    why = md.split("Why it linked")[1]
    assert "mule00@okaxis" in why
    assert "9999900000" not in why  # the kingpin bridge is not Layer 1 evidence

    lead = "\n".join(w.value for w in at.warning)
    assert "9999900000" in lead and "3 rings" in lead
    assert "not proof" in lead


# ── A10: the bubble must not claim a link it does not make ───────────────────

def test_only_the_identifiers_the_graph_nodes_are_told_to_be_nodes(at_hero):
    """`build_graph` nodes UPI/phone/account/device -- never an amount, never a
    URL. The bubble used to tooltip EVERY highlight "becomes a graph node", so
    the hero's own `Rs 50,000` made a false claim about the one mechanic the
    whole product rests on. Amount and link are now marked as context."""
    import whatsapp
    from src.detector import entity_spans
    from src.graph.build import _NODE_PREFIX

    assert whatsapp.LINKING_KINDS == set(_NODE_PREFIX) - {"device_hint"}

    hero = next(m for m in at_hero.session_state.chat_messages if m["role"] == "out")
    rendered = whatsapp.highlight(hero["text"], entity_spans(hero["text"]))

    for value in ("mule00@okaxis", "+919999900000"):
        i = rendered.index(value)
        tag = rendered.rfind("<span", 0, i)
        assert 'class="ident"' in rendered[tag:i]
        assert "becomes a node in the fraud network" in rendered[tag:i]

    i = rendered.index("Rs 50,000")
    tag = rendered.rfind("<span", 0, i)
    assert 'class="ident ctx"' in rendered[tag:i]
    assert "does not link on it" in rendered[tag:i]


def test_a_shared_url_is_highlighted_but_never_claimed_as_a_link():
    """Two victims naming the same phishing URL do NOT form a ring -- Layer 1
    links only on values that name a payee/person/account (a shared domain is as
    often popularity as identity, the B17 rule). So the bubble must not promise
    a node it will never build."""
    import whatsapp
    from src.detector import detect, entity_spans
    from src.graph import build_graph, detect_rings

    text = "KYC blocked. Click http://sbi-kyc-verify.in/update and pay Rs 499."
    a = detect(text, channel="sms")
    b = detect("Account suspended. Visit http://sbi-kyc-verify.in/update now.", channel="sms")
    assert a.entities.url == b.entities.url  # extracted, and identical
    assert detect_rings(build_graph([a, b])) == []  # yet they link to nothing

    rendered = whatsapp.highlight(text, entity_spans(text))
    i = rendered.index("http://sbi-kyc-verify.in/update")
    tag = rendered.rfind("<span", 0, i)
    assert 'class="ident ctx"' in rendered[tag:i]
    assert "does not link on it" in rendered[tag:i]


def test_the_legend_separates_linking_identifiers_from_context(at_hero):
    import whatsapp

    legend = whatsapp.legend()
    links, context = legend.split("Extracted, but never a link")
    for label in ("UPI", "phone", "account"):
        assert label in links
    for label in ("link", "amount"):
        assert label in context
        assert label not in links.split("this is what links rings:")[1]
    assert 'class="wa-legend"' in _html(at_hero)  # and it is actually rendered


# ── A11: one report that bridges two known rings ─────────────────────────────

def test_a_report_bridging_two_rings_is_announced_as_a_merge(at_two_mules):
    """Naming two known mules fuses R0000 (30) and R0001 (14) into one 45-incident
    ring. The page used to call that a plain "linked to ring R0000" -- under-claiming
    the strongest thing the product can do -- and derived its "+N" delta from an
    arbitrary member of a frozenset, so the number flickered across processes
    once the merged rings differed in size. They differ now, by construction."""
    assert not at_two_mules.exception

    join = at_two_mules.session_state.last_join
    assert join["merged"] == 2
    # before = the LARGEST ring absorbed, not an arbitrary one: deterministic
    assert join["before"] == 30 and join["after"] == 45

    m = _metrics(at_two_mules)
    assert m["Incidents in this ring"].value == "45"
    assert m["Shared hard identifiers"].value == "2"
    assert any("merged 2 known rings" in e.value.lower() for e in at_two_mules.error)

    md = "\n".join(x.value for x in at_two_mules.markdown)
    for mule in ("mule00@okaxis", "mule01@okaxis"):
        assert mule in md.split("Why it linked")[1]


# ── B21: the legit hub is never credited with a Layer 1 link ─────────────────

def test_naming_the_legit_hub_alongside_the_mule_does_not_credit_the_hub(at_hub_and_mule):
    assert not at_hub_and_mule.exception
    md = "\n".join(x.value for x in at_hub_and_mule.markdown)
    why = md.split("Why it linked")[1]
    assert "mule00@okaxis" in why
    assert "swiggy" not in why  # Layer 1 excluded it; the screen must agree
    assert _metrics(at_hub_and_mule)["Shared hard identifiers"].value == "1"


# ── A5: a message that links to nothing must not crash the Command centre ────

def test_the_decoy_is_not_flagged_and_links_to_nothing(at_decoy):
    assert not at_decoy.exception
    blob = _html(at_decoy)
    assert "Looks legitimate" in blob and "Scam detected" not in blob
    assert at_decoy.session_state.last_join["ring_id"] is None
    assert any("One report is not a ring" in i.value for i in at_decoy.info)


def test_an_unlinked_report_does_not_crash_the_command_centre(at_decoy):
    """`last_join` carries no before/after when nothing linked, and the Command
    centre subtracted them anyway -- KeyError. Reachable two ways on stage: the
    decoy pill, and any judge who types their own text without naming a mule."""
    at = at_decoy.switch_page("app_pages/command_centre.py").run()
    assert not at.exception
    assert all(m.delta in (None, "") for m in at.metric if m.label == "Largest ring")


def test_the_hero_still_claims_its_growth_on_the_command_centre():
    at = _run(pill=HERO_PILL).switch_page("app_pages/command_centre.py").run()
    assert not at.exception
    assert len(at.tabs) == 4
    assert any(m.label == "Largest ring" and m.delta == "1" for m in at.metric)


def test_the_kingpin_disclaimer_is_rendered_in_full(at_idle):
    """Hard rule (CLAUDE.md §2.5): Layer 2 is a lead, not proof, and the
    disclaimer is never truncated."""
    at = at_idle.switch_page("app_pages/command_centre.py").run()
    assert not at.exception
    captions = [c.value for c in at.caption]
    assert any(
        "NOT legal proof" in c
        and "corroborated with independent evidence" in c
        and c.endswith("before any action.")
        for c in captions
    )
    # the evidence pack's integrity hash is on screen (G3)
    assert any(len(m.value) > 40 for m in at.markdown)


# ── A1 + G1: the lead-time replay ────────────────────────────────────────────

def test_the_replay_ring_is_the_mule_never_the_legit_hub(at_idle):
    """The page used to resolve the ring's payee as the first Layer 1 ring in
    arrival order, which picked up a 2-report legit-hub component long before
    the hub's degree reached the cap -- putting `swiggy@ybl` on stage as a fraud
    ring of 102, the exact false positive the guardrail exists to prevent. It now
    takes the ring from batch Layer 1 at the demo cap, and rings are hub-pruned,
    so a legit hub cannot be in one to be named."""
    at = at_idle.switch_page("app_pages/replay.py").run()
    assert not at.exception

    banner = "\n".join(e.value for e in at.error)
    assert "mule00@okaxis" in banner and "swiggy" not in banner

    m = _metrics(at)
    assert m["Reports received"].value == "30"
    assert m["Victims after the flag"].value == "28"
    assert any("28 subsequent victims were preventable" in s.value for s in at.success)


def test_the_replay_runs_on_the_same_world_the_rest_of_the_app_draws(at_idle):
    """The closer used to be measured on a network generated only for that page
    (one ring, 30 victims), because the old cap of 10 made any ring bigger than 10
    undetectable in batch -- its own mule UPI exceeded the cap and was pruned as a
    hub. A judge therefore saw the hero join a ring of 5, then a ring of 30 on the
    lead-time page: two different universes wearing the same mule's name."""
    at = at_idle.switch_page("app_pages/replay.py").run()
    replayed = _metrics(at)["Reports received"].value

    home = at_idle.switch_page("app_pages/live.py").run()
    largest = _metrics(home)["Rings in the intelligence base"]  # idle: no join yet
    assert largest.value == "6"
    # the ring being replayed is the ring the hero joins, at its pre-join size
    assert replayed == "30"


def test_the_replay_flags_the_ring_at_the_second_report(at_idle):
    at = at_idle.switch_page("app_pages/replay.py").run()

    at.slider[0].set_value(1).run()
    assert _metrics(at)["Ring detected?"].value == "Not yet"
    assert any("not a ring" in i.value for i in at.info)

    at.slider[0].set_value(2).run()
    assert _metrics(at)["Ring detected?"].value == "Yes"
