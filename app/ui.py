"""Shared visual chrome: the Detect->Link->Prove pipeline strip, the two-layer
doctrine cards, and the card wrapper. Presentation only -- every value shown
arrives pre-computed from `src/` calls or session state, so nothing in this
file can create or alter a claim (§17 applies to the UI too).

HTML builders are pure functions of their inputs; `st.html` wrappers sit next
to them so pages stay one-liners and tests can assert on the strings directly.
"""
from __future__ import annotations

import streamlit as st

# Stage identity colours. Detect wears the primary-linker blue on purpose --
# the sensor exists to feed identifiers to the graph; Link wears the phone
# purple; Prove the advice teal. All three already appear in the app with
# these meanings (whatsapp.IDENT_COLORS / .wa-advice), so no new hues.
_STAGES = (
    ("DETECT", "📡", "#38bdf8", "rgba(56,189,248,.35)",
     "text in → verdict + extracted identifiers"),
    ("LINK", "🕸️", "#a78bfa", "rgba(167,139,250,.35)",
     "shared identifiers → rings"),
    ("PROVE", "⚖️", "#2dd4bf", "rgba(45,212,191,.35)",
     "ring → court-ready evidence pack"),
)

CSS = """
<style>
/* Streamlit leaves ~5rem of dead padding under the fixed top nav; reclaiming
   some of it buys every page fold space -- which is what keeps the kingpin
   banner on-screen at 1000px on the Live page (§16.6). Not less than 4rem:
   the nav is a fixed overlay 3.75rem tall, and below that the first element
   on every page (the pipeline strip) slides underneath it. */
[data-testid="stMainBlockContainer"] { padding-top: 4rem; }
/* compact on purpose: this strip sits above the hero screen, and every pixel
   it takes pushes the kingpin banner toward the fold (§16.6) */
.nw-pipe { display:flex; align-items:stretch; gap:8px; margin:0 0 10px; }
.nw-stage {
  flex:1; min-width:0; display:flex; align-items:center; gap:8px;
  padding:5px 11px; border:1px solid #2a3946; border-radius:10px;
  background:#131b29; opacity:.45;
}
.nw-stage.on {
  opacity:1; border-color:var(--c);
  animation: nw-glow 2.6s ease-in-out infinite alternate;
}
@keyframes nw-glow {
  from { box-shadow:0 0 6px var(--g); }
  to   { box-shadow:0 0 16px var(--g); }
}
.nw-ico { font-size:15px; }
.nw-lab { font-size:12.5px; font-weight:700; letter-spacing:.5px;
          color:#e6edf3; line-height:1.2; min-width:0; }
.nw-lab small { display:block; font-weight:400; letter-spacing:0;
                color:#8696a0; font-size:11px; white-space:nowrap;
                overflow:hidden; text-overflow:ellipsis; }
.nw-tick { margin-left:auto; color:var(--c); font-weight:800; }
.nw-arrow { align-self:center; color:#3d4c63; font-size:16px; flex:0 0 auto; }

.nw-layers { display:flex; flex-wrap:wrap; gap:12px; margin:4px 0 10px; }
.nw-layer {
  flex:1; min-width:260px; padding:10px 14px; border-radius:10px;
  background:#131b29; border:1px solid #2a3946; border-left:4px solid var(--c);
}
.nw-layer-k { font-size:11.5px; font-weight:800; letter-spacing:.8px;
              color:var(--c); margin-bottom:4px; }
.nw-layer-t { font-size:12.8px; color:#b6c2cf; line-height:1.5; }

.nw-card { border:1px solid #2a3946; border-radius:12px; background:#131b29;
           padding:10px 14px 8px; margin:6px 0; }
.nw-card-h { font-size:11.5px; font-weight:700; letter-spacing:.7px;
             text-transform:uppercase; color:#8696a0; }
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def pipeline_html(detected: bool, linked: bool, proved: bool) -> str:
    """The product in one strip. Stages light up as the demo reaches them, so
    the seam between the citizen tool and the network intelligence -- the thing
    the one-screen rebuild exists to show (§16.1) -- is stated by the page
    itself: same report, three stages, no second product."""
    lit = (detected, linked, proved)
    boxes = []
    for (name, ico, c, glow, sub), on in zip(_STAGES, lit):
        boxes.append(
            f'<div class="nw-stage{" on" if on else ""}" style="--c:{c};--g:{glow}" '
            f'title="{name}: {sub}">'
            f'<span class="nw-ico">{ico}</span>'
            f'<span class="nw-lab">{name}<small>{sub}</small></span>'
            + ('<span class="nw-tick">✓</span>' if on else "")
            + "</div>"
        )
    return '<div class="nw-pipe">' + '<div class="nw-arrow">→</div>'.join(boxes) + "</div>"


def pipeline(detected: bool, linked: bool, proved: bool) -> None:
    st.html(pipeline_html(detected, linked, proved))


def layer_cards_html() -> str:
    """The two-layer doctrine -- §3's differentiator -- as a fixture of the
    command centre rather than a caption inside one tab. Qualitative on
    purpose: the measured numbers live in the Validation tab, read from the
    code-produced artifacts."""
    return (
        '<div class="nw-layers">'
        '<div class="nw-layer" style="--c:#38bdf8">'
        '<div class="nw-layer-k">LAYER 1 · STRUCTURAL PROOF · DETERMINISTIC</div>'
        '<div class="nw-layer-t">Rings are connected components over shared hard '
        "identifiers: payee UPI, phone, account, device. No model, no score, "
        "nothing learned: every edge is an itemised, hash-stamped fact in the "
        "evidence pack.</div></div>"
        '<div class="nw-layer" style="--c:#fbbf24">'
        '<div class="nw-layer-k">LAYER 2 · KINGPIN LEAD · AI, NOT PROOF</div>'
        '<div class="nw-layer-t">Centrality across rings ranks which node to '
        "investigate first. It prioritises casework; it is never cited as "
        "evidence, and every lead card carries that disclaimer.</div></div>"
        "</div>"
    )


def layer_cards() -> None:
    st.html(layer_cards_html())


def card(title: str, body_html: str) -> None:
    """A titled dark card around pre-built HTML (the caller owns escaping)."""
    st.html(f'<div class="nw-card"><div class="nw-card-h">{title}</div>{body_html}</div>')
