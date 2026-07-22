"""Shared visual chrome AND the global app theme.

Two jobs:

1. **The design system.** `CSS` restyles Streamlit's own chrome -- the top
   navigation, the sidebar, metrics, tabs, buttons, pills, inputs, expanders,
   alerts, the graph iframe -- onto the same dark tokens the WhatsApp chat panel
   already uses (`whatsapp.py`), so the whole app reads as one designed console
   ("The Wall's watchroom") instead of one custom component marooned in stock
   Streamlit. Tokens live in `:root` as CSS variables; change a colour once, it
   moves everywhere.
2. **The bespoke bits**: the page-header band, the Detect->Link->Prove pipeline
   strip, the two-layer doctrine cards, the sidebar brand lockup, the titled
   card, the honest-scope callout.

Presentation only -- every value shown arrives pre-computed from `src/` calls or
session state, so nothing in this file can create or alter a claim (§17 applies
to the UI too). HTML builders are pure functions of their inputs; `st.html`
wrappers sit next to them so pages stay one-liners and tests can assert on the
strings directly.
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

# The whole design system. Tokens first, then Streamlit-chrome overrides, then
# our bespoke components -- all referencing the tokens so the WhatsApp panel and
# everything around it share one palette, one radius, one type scale.
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --nw-bg:#0b141a;          /* WhatsApp ink -- the base the chat panel already uses */
  --nw-panel:#0f1a21;
  --nw-surface:#16232c;     /* cards */
  --nw-surface-2:#1e2a32;   /* raised: metrics, header, incoming bubble */
  --nw-border:#26333c;
  --nw-border-2:#33454f;
  --nw-hair:rgba(255,255,255,.055);   /* top-edge light-catch on every surface */
  --nw-text:#e9edef;
  --nw-muted:#8696a0;
  --nw-faint:#5b6b76;
  --nw-accent:#00a884;      /* WhatsApp green -- primary actions */
  --nw-accent-2:#4fd1c5;    /* teal -- links, advice, secondary accent */
  --nw-grad:linear-gradient(135deg,#00a884 0%,#4fd1c5 100%);
  --nw-danger:#ef4444;
  --nw-warn:#fbbf24;
  --nw-info:#38bdf8;
  --nw-radius:14px;
  --nw-radius-sm:9px;
  --nw-font:'Inter','Segoe UI',system-ui,-apple-system,'Helvetica Neue',Arial,sans-serif;
  --nw-mono:ui-monospace,'Cascadia Code','SFMono-Regular',Menlo,Consolas,monospace;
  --nw-shadow:0 6px 22px rgba(0,0,0,.35);
  --nw-glass:var(--nw-shadow), inset 0 1px 0 0 var(--nw-hair);
}

/* ---------- base ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
  font-family:var(--nw-font);
}
.stApp {
  background:
    radial-gradient(1150px 600px at 86% -10%, rgba(0,168,132,.11) 0%, transparent 56%),
    radial-gradient(980px 520px at 4% -12%, rgba(79,209,197,.07) 0%, transparent 52%),
    var(--nw-bg);
  background-attachment:fixed;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
  font-family:var(--nw-font); color:var(--nw-text); letter-spacing:-.02em;
  text-wrap:balance;
}
.stApp h1 { font-weight:800; font-size:1.9rem; line-height:1.13; }
.stApp h2 { font-weight:750; }
.stApp h3 { font-weight:700; font-size:1.16rem; }
.stApp a { color:var(--nw-accent-2); text-decoration:none; }
.stApp a:hover { text-decoration:underline; }
[data-testid="stMainBlockContainer"] { padding-top:3.7rem; max-width:1520px; }
[data-testid="stHeader"] { background:transparent; }
:focus-visible { outline:2px solid var(--nw-accent-2); outline-offset:2px; border-radius:4px; }

/* ---------- the top app bar (kills the stock-nav tell) ---------- */
/* Streamlit's Deploy button is a dev-tool artefact, not part of the product --
   hide it; the brand + nav are what this bar is for. */
[data-testid="stAppDeployButton"] { display:none !important; }
[data-testid="stToolbar"] { padding-top:6px; }
/* brand wordmark, far left of the bar (a flex ::before, so no fragile DOM hook) */
[data-testid="stToolbar"]::before {
  content:"NIGHT'S WATCH";
  font:800 13.5px/1 var(--nw-font); letter-spacing:.16em;
  color:var(--nw-text); align-self:center; white-space:nowrap;
  padding:0 20px 0 6px; margin-right:2px;
  border-right:1px solid var(--nw-border);
}
/* nav links -> segmented pills */
[data-testid="stTopNavLink"] {
  border-radius:999px !important; padding:6px 15px !important;
  transition:background .15s ease, color .15s ease;
}
[data-testid="stTopNavLink"] p { font-weight:600 !important; font-size:14px !important; }
[data-testid="stTopNavLink"]:hover { background:rgba(255,255,255,.05) !important; }
[data-testid="stTopNavLink"][aria-current="page"] {
  background:rgba(0,168,132,.16) !important;
  box-shadow:inset 0 0 0 1px rgba(0,168,132,.45);
}
[data-testid="stTopNavLink"][aria-current="page"] p { color:var(--nw-text) !important; }
[data-testid="stMainMenu"] { opacity:.6; }
[data-testid="stMainMenu"]:hover { opacity:1; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background:linear-gradient(180deg,#101c23 0%, var(--nw-bg) 100%);
  border-right:1px solid var(--nw-border);
}
[data-testid="stSidebarUserContent"] { padding-top:.4rem; }

/* ---------- metrics -> glass cards ---------- */
[data-testid="stMetric"] {
  background:linear-gradient(180deg,var(--nw-surface-2),var(--nw-surface));
  border:1px solid var(--nw-border);
  border-radius:var(--nw-radius);
  padding:13px 16px 11px;
  box-shadow:var(--nw-glass);
  transition:border-color .15s ease, transform .12s ease;
}
[data-testid="stMetric"]:hover { border-color:var(--nw-border-2); transform:translateY(-1px); }
[data-testid="stMetricLabel"] p {
  font-size:11.5px; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
  color:var(--nw-muted);
}
[data-testid="stMetricValue"] {
  color:var(--nw-text); font-weight:800; font-size:1.6rem; letter-spacing:-.01em;
  font-variant-numeric:tabular-nums;
}
[data-testid="stMetricDelta"] { font-weight:600; font-variant-numeric:tabular-nums; }

/* ---------- tabs -> segmented control ---------- */
[data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid var(--nw-border); }
button[data-baseweb="tab"] {
  color:var(--nw-muted); font-weight:600; padding:8px 12px;
  border-radius:9px 9px 0 0;
}
button[data-baseweb="tab"]:hover { color:var(--nw-text); background:rgba(255,255,255,.03); }
button[data-baseweb="tab"][aria-selected="true"] { color:var(--nw-text); }
[data-baseweb="tab-highlight"] { background:var(--nw-accent) !important; height:3px; border-radius:3px 3px 0 0; }
[data-baseweb="tab-border"] { display:none; }

/* ---------- buttons ---------- */
.stButton>button, [data-testid="stDownloadButton"]>button {
  border-radius:var(--nw-radius-sm);
  border:1px solid var(--nw-border);
  background:var(--nw-surface-2);
  color:var(--nw-text);
  font-weight:600;
  box-shadow:inset 0 1px 0 0 var(--nw-hair);
  transition:border-color .15s ease, background .15s ease, transform .04s ease;
}
.stButton>button:hover, [data-testid="stDownloadButton"]>button:hover {
  border-color:var(--nw-accent); background:#243139;
}
.stButton>button:active, [data-testid="stDownloadButton"]>button:active { transform:translateY(1px); }
/* download = the payoff action, give it the accent */
[data-testid="stDownloadButton"]>button {
  border-color:rgba(0,168,132,.4); background:rgba(0,168,132,.12); color:#d6f5ec;
}
[data-testid="stDownloadButton"]>button:hover { background:rgba(0,168,132,.2); border-color:var(--nw-accent); }

/* ---------- pills (st.pills / button group) ---------- */
[data-testid="stButtonGroup"] button {
  border-radius:999px !important;
  border:1px solid var(--nw-border) !important;
  background:var(--nw-surface-2) !important;
  color:var(--nw-text) !important;
  font-weight:600;
}
[data-testid="stButtonGroup"] button[aria-checked="true"] {
  border-color:var(--nw-accent) !important;
  background:rgba(0,168,132,.18) !important;
}

/* ---------- inputs ---------- */
[data-testid="stChatInput"] {
  border-radius:999px; border:1px solid var(--nw-border); background:var(--nw-surface-2);
}
[data-testid="stChatInput"] textarea { color:var(--nw-text); }
[data-baseweb="select"] > div, [data-baseweb="input"] > div {
  border-radius:var(--nw-radius-sm) !important; border-color:var(--nw-border) !important;
  background:var(--nw-surface-2) !important;
}

/* ---------- bordered containers -> glass ---------- */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:var(--nw-radius) !important; }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-color:var(--nw-border) !important; }

/* ---------- expander ---------- */
[data-testid="stExpander"] details {
  border:1px solid var(--nw-border); border-radius:var(--nw-radius);
  background:var(--nw-surface); overflow:hidden; box-shadow:inset 0 1px 0 0 var(--nw-hair);
}
[data-testid="stExpander"] summary { font-weight:600; padding:10px 14px; }
[data-testid="stExpander"] summary:hover { color:var(--nw-accent-2); }

/* ---------- alerts: keep the semantic hue, refine shape ---------- */
[data-testid="stAlertContainer"] {
  border-radius:var(--nw-radius); border:1px solid var(--nw-border);
  box-shadow:var(--nw-glass);
}

/* ---------- graph iframe blends into the page ---------- */
.stApp iframe { border-radius:var(--nw-radius); border:1px solid var(--nw-border); }

/* ---------- captions, rules, code, page links ---------- */
[data-testid="stCaptionContainer"], .stCaption { color:var(--nw-muted) !important; }
hr, [data-testid="stDivider"] hr { border-color:var(--nw-border) !important; }
code {
  background:rgba(255,255,255,.06); border:1px solid var(--nw-border);
  border-radius:6px; padding:.5px 5px; color:#cfe6de; font-size:.86em;
  font-family:var(--nw-mono);
}
[data-testid="stPageLink"] a { color:var(--nw-accent-2); font-weight:600; }

/* ---------- the page-header band ---------- */
.nw-head { margin:0 0 16px; padding:2px 0 13px; border-bottom:1px solid var(--nw-border); }
.nw-eyebrow {
  display:flex; align-items:center; gap:9px;
  font:700 11px/1 var(--nw-font); letter-spacing:.16em; text-transform:uppercase;
  color:var(--nw-accent-2); margin-bottom:9px;
}
.nw-eyebrow::before {
  content:""; width:16px; height:2px; border-radius:2px; background:var(--nw-grad);
}
.nw-title { font:800 1.95rem/1.1 var(--nw-font); letter-spacing:-.022em; color:var(--nw-text); }
.nw-sub { margin-top:7px; color:var(--nw-muted); font-size:13.5px; line-height:1.5; max-width:78ch; }

/* ---------- the sidebar brand lockup + system-status chip ---------- */
.nw-brand { display:flex; align-items:center; gap:11px; padding:6px 2px 2px; }
/* the shield is a pure-CSS clip-path mark: st.html's sanitiser drops any style
   rule carrying a data:/url() value (SVG or otherwise), so the emblem uses only
   a gradient + polygon -- nothing to strip, crisp at any DPR, offline-safe */
.nw-brand .nw-emblem { flex:0 0 auto; position:relative; width:24px; height:28px;
  background:var(--nw-grad);
  clip-path:polygon(50% 0%, 100% 15%, 100% 56%, 50% 100%, 0% 56%, 0% 15%); }
.nw-brand .nw-emblem::after {  /* the sentinel eye, punched dark */
  content:""; position:absolute; left:50%; top:42%; width:6px; height:6px;
  transform:translate(-50%,-50%); border-radius:50%; background:var(--nw-bg); }
.nw-word { font:800 15.5px/1.05 var(--nw-font); letter-spacing:.11em; color:var(--nw-text); }
.nw-tag { font:600 10.5px/1.3 var(--nw-font); letter-spacing:.03em; color:var(--nw-muted); margin-top:3px; }
.nw-oath { font-size:12px; font-style:italic; color:var(--nw-faint); margin:6px 2px 2px; }
.nw-sysstat {
  display:flex; align-items:center; gap:10px; margin:14px 0 4px;
  padding:10px 12px; border-radius:var(--nw-radius-sm);
  background:var(--nw-surface); border:1px solid var(--nw-border);
  box-shadow:inset 0 1px 0 0 var(--nw-hair);
}
.nw-sys-k { font:700 9.5px/1 var(--nw-font); letter-spacing:.14em; text-transform:uppercase; color:var(--nw-faint); }
.nw-sys-v { font-size:12.5px; color:var(--nw-text); font-weight:600; margin-top:3px; }
.nw-dot { flex:0 0 auto; width:9px; height:9px; border-radius:50%; background:var(--nw-accent);
          box-shadow:0 0 0 3px rgba(0,168,132,.18); animation:nw-pulse 2.4s ease-in-out infinite; }
.nw-dot.amber { background:var(--nw-warn); box-shadow:0 0 0 3px rgba(251,191,36,.18); }
@keyframes nw-pulse { 0%,100%{opacity:1} 50%{opacity:.45} }

/* ---------- the pipeline strip ---------- */
/* compact on purpose: this strip sits above the hero screen, and every pixel
   it takes pushes the kingpin banner toward the fold (§16.6) */
.nw-pipe { display:flex; align-items:stretch; gap:8px; margin:0 0 12px; }
.nw-stage {
  flex:1; min-width:0; display:flex; align-items:center; gap:9px;
  padding:7px 13px; border:1px solid var(--nw-border); border-radius:12px;
  background:var(--nw-surface); box-shadow:inset 0 1px 0 0 var(--nw-hair); opacity:.62;
  transition:opacity .2s ease, border-color .2s ease;
}
.nw-stage.on {
  opacity:1; border-color:var(--c);
  animation: nw-glow 2.6s ease-in-out infinite alternate;
}
@keyframes nw-glow {
  from { box-shadow:inset 0 1px 0 0 var(--nw-hair), 0 0 5px var(--g); }
  to   { box-shadow:inset 0 1px 0 0 var(--nw-hair), 0 0 15px var(--g); }
}
.nw-ico { font-size:15px; }
.nw-lab { font-size:12.5px; font-weight:700; letter-spacing:.5px;
          color:var(--nw-text); line-height:1.2; min-width:0; }
.nw-lab small { display:block; font-weight:400; letter-spacing:0;
                color:var(--nw-muted); font-size:11px; white-space:nowrap;
                overflow:hidden; text-overflow:ellipsis; }
.nw-tick { margin-left:auto; color:var(--c); font-weight:800; }
.nw-arrow { align-self:center; color:var(--nw-faint); font-size:16px; flex:0 0 auto; }

/* ---------- the two-layer doctrine cards ---------- */
.nw-layers { display:flex; flex-wrap:wrap; gap:12px; margin:4px 0 12px; }
.nw-layer {
  flex:1; min-width:260px; padding:13px 16px; border-radius:var(--nw-radius);
  background:var(--nw-surface); border:1px solid var(--nw-border);
  border-left:4px solid var(--c); box-shadow:var(--nw-glass);
}
.nw-layer-k { font-size:11.5px; font-weight:800; letter-spacing:.8px;
              color:var(--c); margin-bottom:4px; }
.nw-layer-t { font-size:12.8px; color:#b6c2cf; line-height:1.5; }

/* ---------- titled card + scope callout ---------- */
.nw-card { border:1px solid var(--nw-border); border-radius:var(--nw-radius);
           background:var(--nw-surface); padding:13px 16px 10px; margin:6px 0;
           box-shadow:var(--nw-glass); }
.nw-card-h { font-size:11px; font-weight:700; letter-spacing:.12em;
             text-transform:uppercase; color:var(--nw-muted); }
.nw-scope { background:var(--nw-surface); border:1px solid var(--nw-border);
            border-left:4px solid var(--nw-accent-2); border-radius:var(--nw-radius);
            padding:13px 16px; margin:6px 0 12px; font-size:13.2px; color:#c7d2d8;
            line-height:1.55; box-shadow:var(--nw-glass); }
.nw-scope b { color:var(--nw-text); }

@media (prefers-reduced-motion: reduce) {
  .nw-stage.on, .nw-dot { animation:none !important; }
  [data-testid="stMetric"]:hover { transform:none; }
}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    """The designed page-header band: a tracked accent eyebrow, the title, and a
    supporting line, with an accent rule under it. Replaces the stock `st.title`
    so every page opens with the same console identity instead of a bare H1.
    (Not used on the Live page, whose fold is measured to the pixel -- §16.6.)"""
    sub = f'<div class="nw-sub">{subtitle}</div>' if subtitle else ""
    st.html(
        '<div class="nw-head">'
        f'<div class="nw-eyebrow">{eyebrow}</div>'
        f'<div class="nw-title">{title}</div>'
        f"{sub}</div>"
    )


def sidebar_brand(status_label: str, *, live: bool) -> None:
    """The brand lockup + a live system-status chip, for the sidebar. `live` ==
    the LLM path is active (green pulse); otherwise the deterministic rules floor
    (amber) -- both are 'up', the colour just says which sensor is running."""
    dot = "nw-dot" if live else "nw-dot amber"
    st.html(
        '<div class="nw-brand">'
        '<span class="nw-emblem"></span>'
        '<span><span class="nw-word">NIGHT\'S WATCH</span>'
        '<div class="nw-tag">Digital Public Safety Intelligence</div></span>'
        "</div>"
        '<div class="nw-oath">The shield that guards the realms of men.</div>'
        '<div class="nw-sysstat">'
        f'<span class="{dot}"></span>'
        '<span><div class="nw-sys-k">Classifier</div>'
        f'<div class="nw-sys-v">{status_label}</div></span>'
        "</div>"
    )


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


def scope_note(body_html: str) -> None:
    """A left-accented callout for an honest-scope statement (the caller owns
    escaping; body is trusted static copy)."""
    st.html(f'<div class="nw-scope">{body_html}</div>')


# ── charts ──────────────────────────────────────────────────────────────────
# Altair is the one surface that still rendered as stock Streamlit: a near-white
# default view, default sans font, hard black axes. `style_chart` restyles any
# chart (single-view OR layered) onto the same tokens as everything else -- a
# transparent surface so the page gradient shows through, Inter type, faint
# gridlines, muted labels. Presentation only: it never touches the data, just
# the paint (§17). Callers pass the ring palette (core.RING_PALETTE) as the
# colour range where a bar must read as the same ring as its graph cluster.
_CHART_FONT = "Inter, 'Segoe UI', system-ui, sans-serif"


def style_chart(chart, *, height: int = 260):
    """Apply the dark design tokens to an Altair chart. Accepts a single-view or
    layered chart; `configure_*` is valid on either because both are top-level."""
    return (
        chart.properties(height=height, background="rgba(0,0,0,0)")
        .configure_view(strokeWidth=0)
        .configure_axis(
            grid=True, gridColor="#1b2831", gridOpacity=0.9, gridWidth=1,
            domainColor="#2a3942", tickColor="#2a3942",
            labelColor="#8696a0", titleColor="#aebdc7",
            labelFont=_CHART_FONT, titleFont=_CHART_FONT,
            labelFontSize=11, titleFontSize=12, titleFontWeight=600, titlePadding=8,
        )
        .configure_legend(
            labelColor="#c7d2d8", titleColor="#aebdc7",
            labelFont=_CHART_FONT, titleFont=_CHART_FONT,
            labelFontSize=11, titleFontSize=11, symbolStrokeWidth=0,
        )
        .configure_arc(stroke="#0b141a", strokeWidth=2)
        .configure_text(font=_CHART_FONT)
    )
