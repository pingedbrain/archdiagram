"""SVG / HTML output and the stylesheet. Colours come from CSS custom properties so one figure
reads in light and dark themes; every `var()` carries the light value as a fallback, so the CSS
also works on a page that defines none of the tokens.
"""

from __future__ import annotations

import math
import re
from html import escape

from . import icons
from .layout import Layout, PlacedNode, Text, crossings, segments
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
.arch .zone.t-orange { stroke: #E77D02; stroke-width: 1.6; }
.arch .zone.t-green { stroke: #7AA116; stroke-width: 1.6; }
.arch .zone.t-blue { stroke: #248BD2; stroke-width: 1.6; }
.arch .zone.t-purple { stroke: #8C4FFF; stroke-width: 1.6; }
.arch .zone.t-gray { stroke: #879196; stroke-width: 1.6; }
.arch .zone.t-red { stroke: #DD344C; stroke-width: 1.6; }
.arch .legend { fill: var(--sunken); }
.arch .band-t { fill: var(--fg-3); font-size: 11px; font-weight: 600; letter-spacing: .08em; }
.arch .t { fill: var(--fg); font-size: 14px; font-weight: 600; }
.arch .t.mono { font-family: var(--font-mono); font-size: 12.5px; font-weight: 500; }
.arch .gk-t { fill: var(--primary); font-size: 16px; font-weight: 700; }
.arch .s { fill: var(--fg-3); font-size: 11.5px; }
.arch .a { fill: none; stroke: var(--fg-3); stroke-width: 1.4; }
.arch .a.acc { stroke: var(--primary); stroke-width: 2; }
.arch .a.dash { stroke-dasharray: 5 5; }
.arch .a.ants { stroke-dasharray: 6 4; animation: arch-ants .5s linear infinite; }
@keyframes arch-ants { to { stroke-dashoffset: -10; } }
.arch .mk { fill: var(--fg-3); }
.arch .mk-a { fill: var(--primary); }
.arch .mko { fill: none; stroke: var(--fg-3); stroke-width: 1.4; }
.arch .mko-a { fill: none; stroke: var(--primary); stroke-width: 1.6; }
.arch .mkd { fill: var(--fg-3); }
.arch .mkd-a { fill: var(--primary); }
.arch .num { fill: var(--surface); stroke: var(--fg-3); stroke-width: 1.2; }
.arch .num.acc { stroke: var(--primary); }
.arch .num-t { fill: var(--fg); font-size: 10px; font-weight: 700; }
.arch .num-t.acc { fill: var(--primary); }
.arch .l { fill: var(--fg-2); font-size: 11.5px; paint-order: stroke; stroke: var(--surface); stroke-width: 3px; }
.arch .acc-t { fill: var(--primary); font-weight: 600; }
.arch .ink { color: var(--fg); }
.arch .pkt { fill: var(--fg-2); stroke: var(--surface); stroke-width: 1.5; }
.arch .pkt.acc { fill: var(--primary); }
@media (prefers-reduced-motion: reduce) { .arch .pkt { display: none; } .arch .a.ants { animation: none; } }
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


def _unit(a, b) -> tuple[float, float]:
    d = math.dist(a, b) or 1
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


HOP_R = 7  # px radius of the jump arc where a vertical wire hops a horizontal one
TINT_HEX = {"orange": "#E77D02", "green": "#7AA116", "blue": "#248BD2",
            "purple": "#8C4FFF", "gray": "#879196", "red": "#DD344C"}


def _path(points, radius: float = 12, hops: dict | None = None) -> str:
    """Polyline path; interior corners are rounded with a quadratic (the AWS elbow look) and
    `hops` ({segment_index: [(x, y)]}) inserts a jump arc where the wire crosses another."""
    pts = list(points)
    hops = hops or {}
    d = [f"M{_n(pts[0][0])},{_n(pts[0][1])}"]
    if len(pts) < 3 and not hops:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(y0 - y1) < 0.01:
                d.append(f"H{_n(x1)}")
            elif abs(x0 - x1) < 0.01:
                d.append(f"V{_n(y1)}")
            else:
                d.append(f"L{_n(x1)},{_n(y1)}")
        return " ".join(d)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ux, uy = _unit(a, b)
        v = _unit(b, pts[i + 2]) if i + 2 < len(pts) else None
        r = min(radius, math.dist(a, b) / 2, math.dist(b, pts[i + 2]) / 2) if v else 0
        end = (b[0] - ux * r, b[1] - uy * r) if v else b
        for h in sorted(hops.get(i, []), key=lambda p: (p[0] - a[0]) * ux + (p[1] - a[1]) * uy):
            d.append(f"L{_n(h[0] - ux * HOP_R)},{_n(h[1] - uy * HOP_R)}")
            d.append(f"A{HOP_R} {HOP_R} 0 0 1 {_n(h[0] + ux * HOP_R)},{_n(h[1] + uy * HOP_R)}")
        d.append(f"L{_n(end[0])},{_n(end[1])}")
        if v:
            nx = (b[0] + v[0] * r, b[1] + v[1] * r)
            d.append(f"Q{_n(b[0])},{_n(b[1])} {_n(nx[0])},{_n(nx[1])}")
    return " ".join(d)


def _symbol_id(prefix: str, ref: icons.IconRef) -> str:
    return f"{prefix}-{ref.pack}-" + re.sub(r"[^A-Za-z0-9_-]", "-", ref.name)


def svg(spec: Spec, lay: Layout, standalone: bool = False) -> str:
    """The <svg> element. Raises icons.IconError if an icon cannot be resolved or is not fetched."""
    prefix = spec.id_prefix
    order = spec.icons.packs
    refs = {n.id: icons.resolve(n.icon, order) for n in spec.nodes}
    badges = {z.index: icons.resolve(z.zone.badge, order) for z in lay.zones if z.zone.badge}
    if lay.legend:
        badges.update({f"lg{it.index}": icons.resolve(it.item.icon, order) for it in lay.legend.items if it.item.icon})
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

    v = lay.view
    aria = f"{spec.title}: {spec.claim}" if spec.claim else spec.title
    head = '<svg xmlns="http://www.w3.org/2000/svg" class="arch"' if standalone else "<svg"
    out = [f'{head} viewBox="{_n(v.x1)} {_n(v.y1)} {_n(v.x2 - v.x1)} {_n(v.y2 - v.y1)}" role="img" aria-label="{escape(aria)}">']
    if standalone:
        out.append("<style>" + tokens_css() + "\n" + css()
                   + "svg.arch { color: var(--fg-3); background: var(--surface); font-family: var(--font-body); }</style>")
    out.append("<defs>")
    shapes = {"mk": "M0,0 L10,5 L0,10 z", "mko": "M0,0 L10,5 L0,10", "mkd": "M0,5 L5,0 L10,5 L5,10 z"}
    for name, d in shapes.items():
        for acc in ("", "-a"):
            out.append(f'<marker id="{prefix}-{name}{acc}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                       f'orient="auto-start-reverse"><path class="{name}{acc}" d="{d}"/></marker>')
    out += symbols.values()
    out.append("</defs>")

    for b in lay.bands:
        cls = "band" if b.band.style == "solid" else "band b2"
        out.append(f'<rect class="{cls}" x="{_n(b.box.x1)}" y="{_n(b.box.y1)}" width="{_n(b.box.x2 - b.box.x1)}" '
                   f'height="{_n(b.box.y2 - b.box.y1)}" rx="14"/>')
        out.append(_text(b.label))

    for z in sorted(lay.zones, key=lambda p: -(p.box.x2 - p.box.x1) * (p.box.y2 - p.box.y1)):
        cls = {"solid": "zone", "dashed": "zone b2", "dotted": "zone b3"}[z.zone.style]
        if z.zone.tint:
            cls += f" t-{z.zone.tint}"
        fill = f' fill="{TINT_HEX[z.zone.tint]}" fill-opacity="0.08"' if z.zone.style == "solid" and z.zone.tint else ""
        out.append(f'<rect class="{cls}" x="{_n(z.box.x1)}" y="{_n(z.box.y1)}" width="{_n(z.box.x2 - z.box.x1)}" '
                   f'height="{_n(z.box.y2 - z.box.y1)}" rx="10"{fill}/>')
        if z.badge:
            sid = _symbol_id(prefix, badges[z.index])
            w = _n(z.badge.x2 - z.badge.x1)
            use = f'<use href="#{sid}" x="{_n(z.badge.x1)}" y="{_n(z.badge.y1)}" width="{w}" height="{w}"/>'
            out.append(f'<g class="ink">{use}</g>' if "currentColor" in symbols[sid] else use)
        if z.label:
            out.append(_text(z.label))

    hop_map = crossings(lay.edges)
    for e in lay.edges:  # edges first, so icons sit on top
        cls = "a acc" if e.edge.accent else "a"
        mname = {"filled": "mk", "open": "mko", "diamond": "mkd"}[e.edge.arrow]
        marker = f"{prefix}-{mname}{'-a' if e.edge.accent else ''}"
        if e.edge.dashed:
            cls += " dash"
        if e.edge.flow == "ants":
            cls += " ants"
        ends = f' marker-end="url(#{marker})"' + (f' marker-start="url(#{marker})"' if e.edge.both else "")
        if e.edge.flow == "dots" or len(e.points) > 2 or e.index in hop_map:
            eid = f' id="{prefix}-e{e.index}"' if e.edge.flow == "dots" else ""
            out.append(f'<path{eid} class="{cls}" d="{_path(e.points, hops=hop_map.get(e.index))}"{ends}/>')
        else:
            (x1, y1), (x2, y2) = e.points
            out.append(f'<line class="{cls}" x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}"{ends}/>')
        if e.label:
            out.append(_text(e.label))

    for nid, p in lay.nodes.items():
        out += _node(p, refs[nid], symbols[_symbol_id(prefix, refs[nid])], _symbol_id(prefix, refs[nid]))

    seq = 0
    for e in lay.edges:  # sequence chips sit on the wire midpoint
        if not e.edge.num:
            continue
        seq += 1
        (x1, y1), (x2, y2) = max(segments(e.points), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
        mx, my, acc = (x1 + x2) / 2, (y1 + y2) / 2, " acc" if e.edge.accent else ""
        out.append(f'<circle class="num{acc}" cx="{_n(mx)}" cy="{_n(my)}" r="8"/>')
        out.append(f'<text class="num-t{acc}" x="{_n(mx)}" y="{_n(my + 3.5)}" text-anchor="middle">{seq}</text>')

    if lay.legend:
        lb = lay.legend.box
        out.append(f'<rect class="legend" x="{_n(lb.x1)}" y="{_n(lb.y1)}" width="{_n(lb.x2 - lb.x1)}" '
                   f'height="{_n(lb.y2 - lb.y1)}" rx="10"/>')
        for it in lay.legend.items:
            s = it.swatch
            my = (s.y1 + s.y2) / 2
            sample = it.item.sample
            if it.item.icon:
                ref = badges[f"lg{it.index}"]
                sid = _symbol_id(prefix, ref)
                inner = min(18, s.x2 - s.x1)
                use = f'<use href="#{sid}" x="{_n((s.x1 + s.x2) / 2 - inner / 2)}" y="{_n(my - inner / 2)}" width="{_n(inner)}" height="{_n(inner)}"/>'
                out.append(f'<g class="ink">{use}</g>' if "currentColor" in symbols[sid] else use)
            elif sample in ("zone", "zone-dotted"):
                zcls = ("zone b3" if sample == "zone-dotted" else "zone b2") + (f" t-{it.item.tint}" if it.item.tint else "")
                out.append(f'<rect class="{zcls}" x="{_n(s.x1 + 2)}" y="{_n(s.y1 + 2)}" width="{_n(s.x2 - s.x1 - 4)}" '
                           f'height="{_n(s.y2 - s.y1 - 4)}" rx="4"/>')
            else:
                ecls = {"edge": "a", "accent": "a acc", "dashed": "a dash", "dots": "a", "ants": "a ants"}[sample]
                mk_ = mka if sample == "accent" else mk
                out.append(f'<line class="{ecls}" x1="{_n(s.x1)}" y1="{_n(my)}" x2="{_n(s.x2)}" y2="{_n(my)}" marker-end="url(#{mk_})"/>')
                if sample == "dots":
                    out.append(f'<circle class="pkt" r="3.5" cx="{_n((s.x1 + s.x2) / 2)}" cy="{_n(my)}"/>')
            out.append(_text(it.label))

    for e in lay.edges:  # packets last, riding on top of the wire
        if e.edge.flow != "dots":
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
