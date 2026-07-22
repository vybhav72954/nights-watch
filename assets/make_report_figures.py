"""Figures for the formal project report (assets/report.tex).

Every value drawn here is read from the seeded corpus and the graph built from
it, not typed in: run `python assets/make_report_figures.py` from the repo root
to regenerate. Outputs land in assets/report_img/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from src.evidence import DEMO_HUB_DEGREE_CAP
from src.evidence.pack import build_evidence_pack
from src.generate.network import generate_network
from src.graph import build_graph, detect_rings

OUT = Path("assets/report_img")
INK = "#123a4a"
LINK = "#0f766e"
GREY = "#8a8f98"


def _state():
    reports = generate_network(seed=0)
    g = build_graph(reports)
    rings = detect_rings(g, hub_degree_cap=DEMO_HUB_DEGREE_CAP)
    return reports, g, rings


def linking_mechanic(g, rings, path: Path) -> None:
    """The bipartite mechanic: shared identifier links, capped hub does not."""
    ring = max(rings, key=lambda r: len(r.incident_ids))
    shared = sorted(n for n in ring.identifier_nodes if n.startswith("upi:"))[0]
    members = sorted(n for n in g.neighbors(shared) if n.startswith("incident:"))[:3]
    hub = max((n for n in g if n.startswith("upi:")), key=lambda n: g.degree(n))
    hub_users = sorted(n for n in g.neighbors(hub) if n.startswith("incident:"))[:2]

    fig, ax = plt.subplots(figsize=(7.6, 2.9))
    ax.set_axis_off()

    def box(x, y, w, label, sub, colour, faded, mono):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - 0.055), w, 0.11,
                                    boxstyle="round,pad=0.015", facecolor="white",
                                    edgecolor=colour, linewidth=1.5,
                                    linestyle="--" if faded else "-", zorder=3))
        ax.text(x, y, label, ha="center", va="center", fontsize=8, color=colour,
                family="monospace" if mono else None)
        if sub:
            ax.text(x, y - 0.10, sub, ha="center", va="top", fontsize=7.5, color=colour)

    def incident(x, y, label, faded=False):
        box(x, y, 0.19, label, None, GREY if faded else INK, faded, True)

    def identifier(x, y, label, sub, faded=False):
        box(x, y, 0.26, label, sub, GREY if faded else LINK, faded, True)

    for y, node in zip([0.85, 0.60, 0.35], members):
        incident(0.12, y, node.replace("incident:", "")[:8])
        ax.plot([0.215, 0.35], [y, 0.60], color=LINK, linewidth=1.3, zorder=1)
    identifier(0.48, 0.60, shared.split(":", 1)[1], f"degree {g.degree(shared)}")
    ax.annotate("", xy=(0.68, 0.60), xytext=(0.615, 0.60),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=1.2))
    ax.text(0.83, 0.60, f"one Layer 1 ring:\n{len(ring.incident_ids)} incidents",
            ha="center", va="center", fontsize=8.5, color=INK, weight="bold")

    for y, node in zip([-0.10, -0.35], hub_users):
        incident(0.12, y, node.replace("incident:", "")[:8], faded=True)
        ax.plot([0.215, 0.35], [y, -0.225], color=GREY, linewidth=1.1,
                linestyle="--", zorder=1)
    identifier(0.48, -0.225, hub.split(":", 1)[1], f"degree {g.degree(hub)}", faded=True)
    ax.plot([0.615, 0.68], [-0.225, -0.225], color=GREY, linewidth=1.1, linestyle=":")
    ax.text(0.83, -0.225,
            f"degree {g.degree(hub)} > cap {DEMO_HUB_DEGREE_CAP}:\nexcluded, forms no ring",
            ha="center", va="center", fontsize=8.5, color=GREY)

    ax.text(0.12, 1.03, "incidents", ha="center", fontsize=8.5, color=INK, style="italic")
    ax.text(0.48, 1.03, "identifiers", ha="center", fontsize=8.5, color=LINK, style="italic")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(-0.52, 1.10)
    fig.tight_layout(pad=0.15)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def degree_hierarchy(g, rings, path: Path) -> None:
    """The one-dimensional scale the hub-degree cap is positioned within."""
    ring = max(rings, key=lambda r: len(r.incident_ids))
    mule = sorted(n for n in ring.identifier_nodes if n.startswith("upi:"))[0]
    phones = sorted((g.degree(n), n) for n in g if n.startswith("phone:"))
    merchants = sorted((g.degree(n), n) for n in g if n.startswith("upi:"))
    hub_deg, hub = merchants[-1]
    mids = [d for d, n in merchants[:-1] if d > DEMO_HUB_DEGREE_CAP]

    rows = [
        (g.degree(mule), f"largest ring's shared payee ({g.degree(mule)})", LINK, "right", 0.30),
        (phones[-1][0], f"planted controller's phone ({phones[-1][0]})", "#b45309", "left", -0.36),
        (min(mids), f"popular payees ({min(mids)} to {max(mids)})", GREY, "left", 0.30),
        (hub_deg, f"legitimate high-volume payee ({hub_deg})", GREY, "right", -0.80),
    ]
    fig, ax = plt.subplots(figsize=(8.0, 2.0))
    ax.axvspan(20, DEMO_HUB_DEGREE_CAP, color=LINK, alpha=0.06)
    for deg, label, colour, ha, dy in rows:
        ax.plot([deg], [0], marker="o", markersize=8, color=colour, zorder=3)
        ax.annotate(label, (deg, dy), ha=ha, va="center", fontsize=8.5, color=colour)
    ax.axvline(DEMO_HUB_DEGREE_CAP, color=INK, linestyle="--", linewidth=1.4)
    ax.annotate(f"cap = {DEMO_HUB_DEGREE_CAP}", (DEMO_HUB_DEGREE_CAP, 0.78),
                ha="center", fontsize=9, color=INK, weight="bold")
    ax.annotate("Layer 1 links here", (21, 0.78),
                ha="left", va="center", fontsize=8, color=LINK, style="italic")
    ax.set_yticks([])
    ax.set_ylim(-1.15, 1.0)
    ax.set_xlim(20, hub_deg * 1.25)
    ax.set_xscale("log")
    ax.set_xticks([30, 40, 53, 70, 100, 178])
    ax.set_xticklabels(["30", "40", "53", "70", "100", "178"])
    ax.set_xlabel("node degree, seeded network at seed 0 (log scale)", fontsize=9)
    for side in ("left", "right", "top"):
        ax.spines[side].set_visible(False)
    fig.tight_layout(pad=0.3)
    fig.savefig(path, dpi=200)
    plt.close(fig)


def evidence_pack_page(reports, g, rings, path: Path) -> None:
    """The proof-carrying pages of the real generated evidence pack, side by side:
    shared identifiers + methodology + per-incident hashes, and the certificate."""
    import fitz
    from PIL import Image

    ring = max(rings, key=lambda r: len(r.incident_ids))
    by_id = {r.report_id: r for r in reports}
    pdf = OUT / "_pack.pdf"
    build_evidence_pack(ring, g, by_id).to_pdf(pdf)
    doc = fitz.open(pdf)

    def crop(page, top_text, height=None):
        """Vertical slice of a page from one of its headings, ending at the last
        line of real content (or after `height` points, for an excerpt)."""
        y0 = page.search_for(top_text)[0].y0 - 14
        content_end = max(b[3] for b in page.get_text("blocks")) + 8
        y1 = min(y0 + height, content_end) if height else content_end
        pix = page.get_pixmap(dpi=190, clip=fitz.Rect(40, y0, page.rect.x1 - 40, y1))
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    tiles = [
        crop(doc[1], "Per-incident integrity", height=97),
        crop(doc[1], "Shared identifiers"),
        crop(doc[2], "Certificate"),
    ]
    doc.close()
    pdf.unlink()

    gap = 26
    w = max(t.width for t in tiles)
    h = sum(t.height for t in tiles) + gap * (len(tiles) - 1)
    canvas = Image.new("RGB", (w, h), "white")
    y = 0
    for t in tiles:
        canvas.paste(t, (0, y))
        y += t.height + gap
    canvas.save(path)


def report_json(reports, path: Path) -> None:
    """One real synthetic report, ground-truth block included."""
    r = next(r for r in reports if r.gt and r.verdict.is_scam and r.entities.payee_upi)
    d = json.loads(r.model_dump_json())
    d["raw_text"] = d["raw_text"][:64] + " ..."
    d["verdict"]["confidence"] = round(d["verdict"]["confidence"], 2)
    d["extraction_confidence"] = round(d["extraction_confidence"], 2)

    def render(obj, indent=0):
        pad = " " * indent
        if isinstance(obj, dict):
            lines = []
            for k, v in obj.items():
                flat = json.dumps(v)
                if not isinstance(v, dict) or len(flat) + len(k) + indent < 74:
                    lines.append(f'{pad}  "{k}": {flat},')
                else:
                    lines.append(f'{pad}  "{k}": {{')
                    lines.extend(render(v, indent + 2))
                    lines.append(f"{pad}  }},")
            lines[-1] = lines[-1].rstrip(",")
            return lines
        return [f"{pad}  {json.dumps(obj)}"]

    path.write_text("{\n" + "\n".join(render(d)) + "\n}\n", encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    reports, g, rings = _state()
    linking_mechanic(g, rings, OUT / "10_linking_mechanic.png")
    degree_hierarchy(g, rings, OUT / "11_degree_hierarchy.png")
    evidence_pack_page(reports, g, rings, OUT / "12_evidence_pack.png")
    report_json(reports, OUT / "report_example.json")
    print("figures written to", OUT)
