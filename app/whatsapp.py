"""The faked WhatsApp panel (CLAUDE.md §8: fake the chat UI, never integrate
the real Meta API).

Two jobs, and the second one is the point of the whole demo:

1. Make beat 1 land emotionally -- a judge should recognise the message shape
   before they read a word of it.
2. **Highlight the extracted identifiers in place, inside the bubble.** The
   graph runs on those values, not on the verdict (CLAUDE.md §1), so showing
   the text literally becoming graph nodes is what makes Detect->Link read as
   one product instead of two demos stapled together.

Identifier colours here are the contract with `core.IDENT_COLORS` -- the same
kind is the same colour in the bubble and in the network.
"""
from __future__ import annotations

import html as _html
from datetime import datetime

import streamlit as st

from src.detector import EntitySpan
from src.schema import Report

# One colour per identifier KIND, shared with the graph legend (core.py).
IDENT_COLORS: dict[str, str] = {
    "payee_upi": "#38bdf8",  # the primary linker -- this is the one that joins rings
    "phone": "#a78bfa",
    "account": "#fbbf24",
    "ifsc": "#fbbf24",
    "url": "#f472b6",
    "amount": "#f87171",
}
IDENT_LABELS: dict[str, str] = {
    "payee_upi": "UPI",
    "phone": "phone",
    "account": "account",
    "ifsc": "IFSC",
    "url": "link",
    "amount": "amount",
}

# The kinds that actually become nodes in the fraud network -- exactly the keys
# of `src.graph.build._NODE_PREFIX`. `url` and `amount` are extracted, carried
# on the report and shown here, but Layer 1 deliberately does NOT link on them:
# a round number links nothing, and a shared URL is as often popularity (a brand
# domain, a shortener) as identity -- the same reason an email is not a UPI
# (CLAUDE.md B17). Layer 1 is the layer that must not guess, so it links only on
# values that name a payee, a person or an account.
#
# This set is the whole point of the distinction: the bubble used to tooltip
# EVERY highlight "becomes a graph node", which made the hero's own `Rs 50,000`
# a false claim about the one mechanic the product rests on.
LINKING_KINDS = frozenset({"payee_upi", "phone", "account", "ifsc"})

# WhatsApp dark-mode palette.
_WA_HEADER = "#202c33"
_WA_CHAT_BG = "#0b141a"
_WA_OUT = "#005c4b"  # outgoing (the citizen's forward)
_WA_IN = "#202c33"  # incoming (Night's Watch reply)
_WA_TEXT = "#e9edef"
_WA_MUTED = "#8696a0"
_WA_TICK = "#53bdeb"

CSS = f"""
<style>
.wa-phone {{
  border: 1px solid #2a3942;
  border-radius: 14px;
  overflow: hidden;
  background: {_WA_CHAT_BG};
  box-shadow: 0 12px 34px rgba(0,0,0,.45);
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
}}
.wa-header {{
  display: flex; align-items: center; gap: 11px;
  background: {_WA_HEADER}; padding: 10px 14px;
  border-bottom: 1px solid #2a3942;
}}
.wa-avatar {{
  width: 38px; height: 38px; border-radius: 50%;
  background: #6a7175; display: flex; align-items: center;
  justify-content: center; font-size: 19px; flex: 0 0 auto;
}}
.wa-who {{ line-height: 1.25; min-width: 0; }}
.wa-name {{ color: {_WA_TEXT}; font-size: 15px; font-weight: 600; }}
.wa-status {{ color: {_WA_MUTED}; font-size: 12px; }}
.wa-actions {{ margin-left: auto; color: {_WA_MUTED}; font-size: 15px; letter-spacing: 3px; }}

/* the doodle wallpaper: faint, cheap, no external asset (offline-safe) */
.wa-body {{
  padding: 16px 12px 20px;
  min-height: 300px;
  background-color: {_WA_CHAT_BG};
  background-image:
    radial-gradient(circle at 12% 22%, rgba(255,255,255,.028) 0 3px, transparent 3px),
    radial-gradient(circle at 68% 58%, rgba(255,255,255,.022) 0 4px, transparent 4px),
    radial-gradient(circle at 38% 82%, rgba(255,255,255,.02) 0 2px, transparent 2px);
  background-size: 140px 140px, 190px 190px, 110px 110px;
}}
.wa-row {{ display: flex; margin-bottom: 10px; }}
.wa-row.out {{ justify-content: flex-end; }}
.wa-bubble {{
  position: relative;
  max-width: 84%;
  padding: 7px 10px 6px;
  border-radius: 9px;
  color: {_WA_TEXT};
  font-size: 14.2px;
  line-height: 1.45;
  word-wrap: break-word;
  box-shadow: 0 1px 1px rgba(0,0,0,.28);
}}
.wa-row.out .wa-bubble {{ background: {_WA_OUT}; border-top-right-radius: 2px; }}
.wa-row.in  .wa-bubble {{ background: {_WA_IN};  border-top-left-radius: 2px; }}
/* bubble tails */
.wa-row.out .wa-bubble::after {{
  content: ""; position: absolute; top: 0; right: -7px;
  border: 7px solid transparent; border-top-color: {_WA_OUT}; border-left-color: {_WA_OUT};
}}
.wa-row.in .wa-bubble::after {{
  content: ""; position: absolute; top: 0; left: -7px;
  border: 7px solid transparent; border-top-color: {_WA_IN}; border-right-color: {_WA_IN};
}}
.wa-fwd {{
  color: {_WA_MUTED}; font-size: 12.5px; font-style: italic;
  display: block; margin-bottom: 3px;
}}
.wa-meta {{
  float: right; margin: 6px 0 -2px 8px;
  color: {_WA_MUTED}; font-size: 11px; white-space: nowrap;
}}
.wa-tick {{ color: {_WA_TICK}; font-size: 12px; }}

/* the load-bearing bit: extracted identifiers, highlighted where they sit */
.ident {{
  border-radius: 3px;
  padding: 0 2px;
  font-weight: 600;
  box-shadow: inset 0 -2px 0 0 currentColor;
  background: rgba(255,255,255,.07);
}}
/* extracted, but NOT a linking identifier (amount, url) -- drawn weaker, with a
   dashed rule, so the eye reads the distinction without needing the tooltip */
.ident.ctx {{
  font-weight: 500;
  box-shadow: none;
  border-bottom: 1px dashed currentColor;
  background: rgba(255,255,255,.04);
}}
.wa-verdict-title {{ font-weight: 700; font-size: 14.5px; display: block; margin-bottom: 4px; }}
.wa-flags {{ margin: 6px 0 2px; }}
.wa-flag {{
  display: inline-block; margin: 2px 3px 2px 0; padding: 1px 7px;
  border-radius: 10px; font-size: 11.5px; font-weight: 600;
  background: rgba(239,68,68,.16); color: #fca5a5; border: 1px solid rgba(239,68,68,.35);
}}
.wa-advice {{
  margin-top: 7px; padding: 7px 9px; border-radius: 6px;
  background: rgba(255,255,255,.05); border-left: 3px solid #4fd1c5;
  font-size: 13.4px; color: #cfd8dd;
}}
.wa-hit {{
  margin-top: 8px; padding: 7px 9px; border-radius: 6px;
  background: rgba(239,68,68,.13); border-left: 3px solid #ef4444;
  font-size: 13.4px; color: #fecaca; font-weight: 600;
}}
.wa-legend {{ font-size: 12px; color: {_WA_MUTED}; margin-top: 8px; }}
/* nowrap: a swatch must never wrap away from the word it labels */
.wa-legend span {{ margin-right: 12px; white-space: nowrap; display: inline-block; }}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def _esc(s: str) -> str:
    return _html.escape(s, quote=False)


def highlight(text: str, spans: list[EntitySpan]) -> str:
    """HTML-escape `text`, then wrap each extracted identifier in a coloured
    mark. Escaping happens per-slice, so an identifier's own characters can
    never be read as markup and untrusted text can never inject any.

    The tooltip is kind-accurate (`LINKING_KINDS`): only the identifiers the
    graph really nodes are told to the judge as such.
    """
    out: list[str] = []
    cursor = 0
    for sp in spans:
        out.append(_esc(text[cursor : sp.start]))
        color = IDENT_COLORS.get(sp.kind, "#94a3b8")
        label = IDENT_LABELS.get(sp.kind, sp.kind)
        links = sp.kind in LINKING_KINDS
        title = (
            f"{label}: extracted; becomes a node in the fraud network"
            if links
            else f"{label}: extracted as context; Layer 1 does not link on it"
        )
        out.append(
            f'<span class="{"ident" if links else "ident ctx"}" style="color:{color}" '
            f'title="{title}">'
            f"{_esc(text[sp.start : sp.end])}</span>"
        )
        cursor = sp.end
    out.append(_esc(text[cursor:]))
    return "".join(out).replace("\n", "<br>")


def _stamp(ts: datetime | None = None) -> str:
    return (ts or datetime.now()).strftime("%H:%M")


def forwarded_bubble(text: str, spans: list[EntitySpan], ts: datetime | None = None) -> str:
    """The citizen's forwarded scam text -- outgoing, with WhatsApp's real
    'Forwarded many times' tag (which is itself a scam tell, so it's honest
    chrome, not decoration)."""
    return (
        '<div class="wa-row out"><div class="wa-bubble">'
        '<span class="wa-fwd">↱ Forwarded many times</span>'
        f"{highlight(text, spans)}"
        f'<span class="wa-meta">{_stamp(ts)} <span class="wa-tick">✓✓</span></span>'
        "</div></div>"
    )


def verdict_bubble(report: Report, advice: str, ring_hit: str | None = None) -> str:
    """Night's Watch's reply -- incoming. Reads `report` only through the
    public verdict/entities surface; `report.gt` is never touched here."""
    v = report.verdict
    if v.is_scam:
        title = '<span class="wa-verdict-title" style="color:#f87171">🚨 Scam detected</span>'
        sub = f"<b>{_esc(v.scam_type.replace('_', ' '))}</b> · confidence {v.confidence:.0%}"
    else:
        title = '<span class="wa-verdict-title" style="color:#4ade80">✅ Looks legitimate</span>'
        sub = f"no scam pattern detected · confidence {v.confidence:.0%}"

    flags = "".join(
        f'<span class="wa-flag">{_esc(f.replace("_", " "))}</span>' for f in v.red_flags
    )
    flags_html = f'<div class="wa-flags">{flags}</div>' if flags else ""
    hit_html = f'<div class="wa-hit">{_esc(ring_hit)}</div>' if ring_hit else ""
    return (
        '<div class="wa-row in"><div class="wa-bubble">'
        f"{title}{sub}{flags_html}"
        f'<div class="wa-advice">{_esc(advice)}</div>'
        f"{hit_html}"
        f'<span class="wa-meta">{_stamp()}</span>'
        "</div></div>"
    )


def phone(bubbles: list[str], *, contact: str, status: str) -> str:
    body = "".join(bubbles) if bubbles else (
        f'<div style="color:{_WA_MUTED};text-align:center;padding:60px 20px;font-size:13.5px">'
        "Forward a suspicious message to check it.<br>Nothing is tapped, tracked, or read "
        "unless you send it."
        "</div>"
    )
    return (
        '<div class="wa-phone">'
        '<div class="wa-header">'
        '<div class="wa-avatar">🛡️</div>'
        f'<div class="wa-who"><div class="wa-name">{_esc(contact)}</div>'
        f'<div class="wa-status">{_esc(status)}</div></div>'
        '<div class="wa-actions">⋮</div>'
        "</div>"
        f'<div class="wa-body">{body}</div>'
        "</div>"
    )


def legend() -> str:
    """Two groups, because they are two different claims -- see `LINKING_KINDS`.
    Saying "highlighted → becomes a node" over all five was simply false for the
    amount and the link, and the amount is highlighted in the hero message."""
    def swatch(k: str) -> str:
        return f'<span style="color:{IDENT_COLORS[k]}">■ {IDENT_LABELS[k]}</span>'

    links = "".join(swatch(k) for k in ("payee_upi", "phone", "account"))
    context = "".join(swatch(k) for k in ("url", "amount"))
    return (
        '<div class="wa-legend">'
        f"<b>Becomes a node in the network</b> (this is what links rings): {links}"
        f"<br><b>Extracted, but never a link</b> (context only): {context}"
        "</div>"
    )
