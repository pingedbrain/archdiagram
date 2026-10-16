"""SVG / HTML output and the stylesheet. Colours come from CSS custom properties so one figure
reads in light and dark themes; every `var()` carries the light value as a fallback, so the CSS
also works on a page that defines none of the tokens.
"""

from __future__ import annotations

import math
import re
from html import escape

from . import icons
from .layout import Layout, PlacedNode, Text
from .spec import Spec

LIGHT = {
    "--bg": "#FDFDFC", "--surface": "#FFFFFF", "--sunken": "#F5F7FA", "--fg": "#0F1729", "--fg-2": "#475467",
    "--fg-3": "#6B7588", "--line": "#E4E9F0", "--primary": "#004FF8", "--primary-soft": "#EFF4FC",
}
DARK = {
    "--bg": "#0C111B", "--surface": "#121927", "--sunken": "#182132", "--fg": "#E8EDF5", "--fg-2": "#B3BDCC",
    "--fg-3": "#8C97A8", "--line": "#253046", "--primary": "#5B8CFF", "--primary-soft": "#16244A",
}
FONTS = {
    "--font-body": '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif',
    "--font-mono": '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
}

_RULES = """\
.arch { margin: 18px 0 22px; }
.arch-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); padding: 12px; }
.arch svg { display: block; width: 100%; min-width: 760px; height: auto; color: var(--fg-3); font-family: var(--font-body); }
.arch .band { fill: var(--sunken); }
.arch .band.b2 { fill: none; stroke: var(--line); stroke-dasharray: 5 5; }
.arch .zone { fill: var(--sunken); }
.arch .zone.b2 { fill: none; stroke: var(--line); stroke-dasharray: 5 5; }
.arch .zone.b3 { fill: none; stroke: var(--fg-3); stroke-width: 2; stroke-dasharray: 0.5 5; stroke-linecap: round; }
.arch .band-t { fill: var(--fg-3); font-size: 11px; font-weight: 600; letter-spacing: .08em; }
.arch .t { fill: var(--fg); font-size: 14px; font-weight: 600; }
.arch .t.mono { font-family: var(--font-mono); font-size: 12.5px; font-weight: 500; }
.arch .gk-t { fill: var(--primary); font-size: 16px; font-weight: 700; }
.arch .s { fill: var(--fg-3); font-size: 11.5px; }
.arch .a { fill: none; stroke: var(--fg-3); stroke-width: 1.4; }
.arch .a.acc { stroke: var(--primary); stroke-width: 2; }
.arch .mk { fill: var(--fg-3); }
.arch .mk-a { fill: var(--primary); }
.arch .l { fill: var(--fg-2); font-size: 11.5px; }
.arch .acc-t { fill: var(--primary); font-weight: 600; }
.arch .ink { color: var(--fg); }
.arch .pkt { fill: var(--fg-2); stroke: var(--surface); stroke-width: 1.5; }
.arch .pkt.acc { fill: var(--primary); }
@media (prefers-reduced-motion: reduce) { .arch .pkt { display: none; } }
.arch .tile { fill: var(--surface); stroke: var(--line); stroke-width: 1.2; }
.arch .gk-ring { fill: var(--primary-soft); stroke: var(--primary); stroke-width: 2; }
.arch figcaption { font-size: 13px; color: var(--fg-2); margin-top: 10px; max-width: 80ch; }
"""


def css() -> str:
    """The .arch rules, each token with its light value as fallback. Paste once per page."""
    table = {**LIGHT, **FONTS}
    return re.sub(r"var\((--[\w-]+)\)", lambda m: f"var({m.group(1)}, {table[m.group(1)]})", _RULES)


def _tokens(selector: str, values: dict) -> str:
    return f"{selector} {{ " + " ".join(f"{k}: {v};" for k, v in values.items()) + " }"


def tokens_css() -> str:
    """Light + dark tokens, following prefers-color-scheme unless data-theme forces one."""
    return "\n".join([
        _tokens(":root", {**LIGHT, **FONTS}),
        "@media (prefers-color-scheme: dark) { " + _tokens(':root:not([data-theme="light"])', {**DARK, "color-scheme": "dark"}) + " }",
        _tokens(':root[data-theme="dark"]', {**DARK, "color-scheme": "dark"}),
    ])


def _n(v: float) -> str:
    return f"{round(v, 2):g}"


def _text(t: Text) -> str:
    return (f'<text class="{t.cls}" x="{_n(t.x)}" y="{_n(t.y)}" text-anchor="{t.anchor}">'
            f"{escape(t.content, quote=False)}</text>")


def _path(points) -> str:
    d = [f"M{_n(points[0][0])},{_n(points[0][1])}"]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if abs(y0 - y1) < 0.01:
            d.append(f"H{_n(x1)}")
        elif abs(x0 - x1) < 0.01:
            d.append(f"V{_n(y1)}")
        else:
            d.append(f"L{_n(x1)},{_n(y1)}")
    return " ".join(d)


def _symbol_id(prefix: str, ref: icons.IconRef) -> str:
    return f"{prefix}-{ref.pack}-" + re.sub(r"[^A-Za-z0-9_-]", "-", ref.name)


def svg(spec: Spec, lay: Layout, standalone: bool = False) -> str:
    """The <svg> element. Raises icons.IconError if an icon cannot be resolved or is not fetched."""
    prefix = spec.id_prefix
    order = spec.icons.packs
    refs = {n.id: icons.resolve(n.icon, order) for n in spec.nodes}
    badges = {z.index: icons.resolve(z.zone.badge, order) for z in lay.zones if z.zone.badge}
    for ref in (*refs.values(), *badges.values()):
        pack = icons.get_pack(ref.pack)
        if not icons.is_fetched(pack):
            raise icons.IconError("icons_missing", f"pack {pack.name} is not in the cache ({icons.pack_dir(pack)})",
                                  f"run: archdiagram icons fetch {pack.name}")
    symbols: dict[str, str] = {}
    for ref in sorted(set(refs.values()) | set(badges.values()), key=lambda r: (r.pack, r.name)):
        pack = icons.get_pack(ref.pack)
        sid = _symbol_id(prefix, ref)
        symbols[sid] = icons.build_symbol(pack, ref, sid, monochrome=ref.pack in spec.icons.monochrome)

    mk, mka = f"{prefix}-mk", f"{prefix}-mk-acc"
    v = lay.view
    aria = f"{spec.title}: {spec.claim}" if spec.claim else spec.title
    head = '<svg xmlns="http://www.w3.org/2000/svg" class="arch"' if standalone else "<svg"
    out = [f'{head} viewBox="{_n(v.x1)} {_n(v.y1)} {_n(v.x2 - v.x1)} {_n(v.y2 - v.y1)}" role="img" aria-label="{escape(aria)}">']
    if standalone:
        out.append("<style>" + tokens_css() + "\n" + css()
                   + "svg.arch { color: var(--fg-3); background: var(--surface); font-family: var(--font-body); }</style>")
    out.append("<defs>")
    for mid, cls in ((mk, "mk"), (mka, "mk-a")):
        out.append(f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                   f'orient="auto-start-reverse"><path class="{cls}" d="M0,0 L10,5 L0,10 z"/></marker>')
    out += symbols.values()
    out.append("</defs>")

    for b in lay.bands:
        cls = "band" if b.band.style == "solid" else "band b2"
        out.append(f'<rect class="{cls}" x="{_n(b.box.x1)}" y="{_n(b.box.y1)}" width="{_n(b.box.x2 - b.box.x1)}" '
                   f'height="{_n(b.box.y2 - b.box.y1)}" rx="14"/>')
        out.append(_text(b.label))

    for z in sorted(lay.zones, key=lambda p: -(p.box.x2 - p.box.x1) * (p.box.y2 - p.box.y1)):
        cls = {"solid": "zone", "dashed": "zone b2", "dotted": "zone b3"}[z.zone.style]
        out.append(f'<rect class="{cls}" x="{_n(z.box.x1)}" y="{_n(z.box.y1)}" width="{_n(z.box.x2 - z.box.x1)}" '
                   f'height="{_n(z.box.y2 - z.box.y1)}" rx="10"/>')
        if z.badge:
            sid = _symbol_id(prefix, badges[z.index])
            w = _n(z.badge.x2 - z.badge.x1)
            use = f'<use href="#{sid}" x="{_n(z.badge.x1)}" y="{_n(z.badge.y1)}" width="{w}" height="{w}"/>'
            out.append(f'<g class="ink">{use}</g>' if "currentColor" in symbols[sid] else use)
        if z.label:
            out.append(_text(z.label))

    for e in lay.edges:  # edges first, so icons sit on top
        cls, marker = ("a acc", mka) if e.edge.accent else ("a", mk)
        if e.edge.flow or len(e.points) > 2:  # flow edges need a <path> for the mpath reference
            eid = f' id="{prefix}-e{e.index}"' if e.edge.flow else ""
            out.append(f'<path{eid} class="{cls}" d="{_path(e.points)}" marker-end="url(#{marker})"/>')
        else:
            (x1, y1), (x2, y2) = e.points
            out.append(f'<line class="{cls}" x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" marker-end="url(#{marker})"/>')
        if e.label:
            out.append(_text(e.label))

    for nid, p in lay.nodes.items():
        out += _node(p, refs[nid], symbols[_symbol_id(prefix, refs[nid])], _symbol_id(prefix, refs[nid]))

    for e in lay.edges:  # packets last, riding on top of the wire
        if not e.edge.flow:
            continue
        length = sum(math.dist(p, q) for p, q in zip(e.points, e.points[1:]))
        dur = max(2, round(length / 80, 1))  # ~80 px/s so every edge moves at the same speed
        n = min(4, max(1, round(length / 160)))
        cls = "pkt acc" if e.edge.accent else "pkt"
        for k in range(n):
            out.append(f'<circle class="{cls}" r="3.5"><animateMotion dur="{dur:g}s" begin="-{round(k * dur / n, 1):g}s" '
                       f'repeatCount="indefinite"><mpath href="#{prefix}-e{e.index}"/></animateMotion></circle>')
    out.append("</svg>")
    return "\n".join(out)


def _node(p: PlacedNode, ref: icons.IconRef, symbol: str, sid: str) -> list[str]:
    pack = icons.get_pack(ref.pack)
    s, cx, cy = p.size, p.cx, p.cy
    out = []
    if p.node.accent:
        h = p.half
        out.append(f'<rect class="gk-ring" x="{_n(cx - h)}" y="{_n(cy - h)}" width="{_n(2 * h)}" height="{_n(2 * h)}" rx="12"/>')
    if pack.tile:
        out.append(f'<rect class="tile" x="{_n(cx - s / 2)}" y="{_n(cy - s / 2)}" width="{_n(s)}" height="{_n(s)}" rx="{_n(s * 0.22)}"/>')
    inner = s * pack.inset
    use = f'<use href="#{sid}" x="{_n(cx - inner / 2)}" y="{_n(cy - inner / 2)}" width="{_n(inner)}" height="{_n(inner)}"/>'
    out.append(f'<g class="ink">{use}</g>' if "currentColor" in symbol else use)
    out += [_text(t) for t in p.texts]
    return out


def fragment(spec: Spec, lay: Layout) -> str:
    cap = f"\n<figcaption>{escape(spec.caption, quote=False)}</figcaption>" if spec.caption else ""
    return f'<figure class="arch">\n<div class="arch-scroll">\n{svg(spec, lay)}\n</div>{cap}\n</figure>\n'


def standalone_svg(spec: Spec, lay: Layout) -> str:
    return svg(spec, lay, standalone=True) + "\n"


def page(spec: Spec, lay: Layout) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(spec.title)}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
{tokens_css()}
* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--fg); font: 15px/1.6 var(--font-body); margin: 0; padding: 32px 16px 64px; }}
main {{ max-width: 1120px; margin-inline: auto; }}
h1 {{ font-size: 22px; margin: 0 0 8px; }}
{css()}</style>
</head>
<body>
<main>
<h1>{escape(spec.title)}</h1>
{fragment(spec, lay)}</main>
</body>
</html>
"""
