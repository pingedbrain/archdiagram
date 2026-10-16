"""Bounding boxes, overlap detection and actionable problem reports.

Suggestions are not guesses: each candidate fix (another label_side, another route, moving a
node half a cell) is applied to a copy of the spec and re-checked, and only fixes that remove
the overlap without adding a new one are offered.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, replace

from . import icons
from .layout import Box, Layout, layout, segments
from .spec import Spec

STROKE = 0.7  # half the edge stroke width, so a line grazing a box counts


@dataclass(frozen=True)
class Problem:
    kind: str
    element: str
    message: str
    suggestion: str
    with_: str = ""
    box: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict:
        return {"kind": self.kind, "element": self.element, "with": self.with_,
                "box": list(self.box) if self.box else None, "message": self.message, "suggestion": self.suggestion}


@dataclass(frozen=True)
class Overlap:
    a: str
    b: str
    a_box: Box
    b_box: Box
    box: Box
    a_text: str = ""
    b_text: str = ""


def _seg_box(p, q) -> Box:
    return Box(min(p[0], q[0]) - STROKE, min(p[1], q[1]) - STROKE, max(p[0], q[0]) + STROKE, max(p[1], q[1]) + STROKE)


def _seg_hits(p, q, b: Box) -> Box | None:
    """Part of segment p-q strictly inside box b (Liang-Barsky clip), as a box, or None."""
    t0, t1 = 0.0, 1.0
    for lo, hi, a, d in ((b.x1 - STROKE, b.x2 + STROKE, p[0], q[0] - p[0]), (b.y1 - STROKE, b.y2 + STROKE, p[1], q[1] - p[1])):
        if abs(d) < 1e-9:
            if not lo < a < hi:
                return None
            continue
        ta, tb = sorted(((lo - a) / d, (hi - a) / d))
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 >= t1:
            return None
    c0 = (p[0] + (q[0] - p[0]) * t0, p[1] + (q[1] - p[1]) * t0)
    c1 = (p[0] + (q[0] - p[0]) * t1, p[1] + (q[1] - p[1]) * t1)
    return _seg_box(c0, c1)


def _collinear(s1, s2) -> Box | None:
    (a, b), (c, d) = s1, s2
    if abs(a[1] - b[1]) < 0.01 and abs(c[1] - d[1]) < 0.01 and abs(a[1] - c[1]) < 3:
        lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
        return Box(lo, min(a[1], c[1]) - 1, hi, max(a[1], c[1]) + 1) if hi - lo > 1 else None
    if abs(a[0] - b[0]) < 0.01 and abs(c[0] - d[0]) < 0.01 and abs(a[0] - c[0]) < 3:
        lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
        return Box(min(a[0], c[0]) - 1, lo, max(a[0], c[0]) + 1, hi) if hi - lo > 1 else None
    return None


def overlaps(lay: Layout) -> list[Overlap]:
    # (name, box, owner, content); owner groups things that may touch each other by design
    texts: list[tuple[str, Box, str, str]] = []
    for nid, p in lay.nodes.items():
        texts += [(t.name, t.box, f"node {nid}", t.content) for t in p.texts]
    for e in lay.edges:
        if e.label:
            texts.append((e.label.name, e.label.box, e.name, e.label.content))
    for b in lay.bands:
        texts.append((b.label.name, b.label.box, f"band {b.index}", b.label.content))
    for z in lay.zones:
        if z.label:
            texts.append((z.label.name, z.label.box, f"zone {z.index}", z.label.content))
    icons_ = [(f"node {nid} icon", p.box, f"node {nid}", "") for nid, p in lay.nodes.items()]
    icons_ += [(f"zone {z.index} badge", z.badge, f"zone {z.index}", "") for z in lay.zones if z.badge]
    solids = texts + icons_

    out: list[Overlap] = []
    for i, (an, ab, ao, at) in enumerate(solids):
        for bn, bb, bo, bt in solids[i + 1:]:
            if ao == bo:
                continue
            hit = ab.intersect(bb)
            if hit:
                out.append(Overlap(an, bn, ab, bb, hit, at, bt))

    for e in lay.edges:
        ends = {f"node {e.edge.src}", f"node {e.edge.dst}"}
        for p, q in segments(e.points):
            for name, box, owner, content in solids:
                if owner == e.name or (name.endswith(" icon") and owner in ends):
                    continue
                hit = _seg_hits(p, q, box)
                if hit:
                    out.append(Overlap(e.name, name, _seg_box(p, q), box, hit, "", content))

    for i, e in enumerate(lay.edges):
        for f in lay.edges[i + 1:]:
            if e.edge.src == f.edge.src or e.edge.dst == f.edge.dst:
                continue  # a fork or a merge shares its trunk on purpose
            for s1 in segments(e.points):
                for s2 in segments(f.points):
                    hit = _collinear(s1, s2)
                    if hit:
                        out.append(Overlap(e.name, f.name, _seg_box(*s1), _seg_box(*s2), hit))

    for i, b in enumerate(lay.bands):
        for c in lay.bands[i + 1:]:
            hit = b.box.intersect(c.box)
            if hit:
                out.append(Overlap(f"band {b.index}", f"band {c.index}", b.box, c.box, hit))

    # zones are containers: a solid must sit fully inside or outside, never across the border
    for z in lay.zones:
        for name, box, owner, content in solids:
            if owner == f"zone {z.index}":
                continue
            hit = box.intersect(z.box)
            if hit and not z.box.contains(box):
                out.append(Overlap(name, f"zone {z.index}", box, z.box, hit, content))
        for w in lay.zones[z.index + 1:]:
            hit = z.box.intersect(w.box)
            if hit and not (z.box.contains(w.box) or w.box.contains(z.box)):
                out.append(Overlap(f"zone {z.index}", f"zone {w.index}", z.box, w.box, hit))
        for b in lay.bands:
            hit = z.box.intersect(b.box)
            if hit and not (z.box.contains(b.box) or b.box.contains(z.box)):
                out.append(Overlap(f"band {b.index}", f"zone {z.index}", b.box, z.box, hit))
    return out


# ------------------------------------------------------------------ suggestions


def _fmt(v: float) -> str:
    return f"{v:g}"


def _with_node(spec: Spec, nid: str, **changes) -> Spec:
    return replace(spec, nodes=tuple(replace(n, **changes) if n.id == nid else n for n in spec.nodes))


def _with_edge(spec: Spec, index: int, **changes) -> Spec:
    return replace(spec, edges=tuple(replace(e, **changes) if i == index else e for i, e in enumerate(spec.edges)))


def _candidates(spec: Spec, lay: Layout, element: str):
    """(description, modified spec) for fixes that touch `element`."""
    words = element.split(" ")
    if words[0] == "edge":
        edge = next((e for e in lay.edges if element in (e.name, f"{e.name} label")), None)
        if edge is None:
            return
        if element.endswith(" label"):
            for side in ("above", "below", "left", "right"):
                if side != edge.edge.label_side:
                    yield f"set label_side: {side} on {edge.name}", _with_edge(spec, edge.index, label_side=side)
        elif not edge.edge.via:
            for r in ("hv", "vh"):
                if r != edge.edge.route:
                    yield f"set route: {r} on {edge.name}", _with_edge(spec, edge.index, route=r)
        return
    if words[0] == "node":
        node = spec.node(words[1])
        if node is None:
            return
        if words[-1] in ("label", "sub"):
            for side in ("below", "left", "right"):
                if side != node.label_side:
                    yield f"set label_side: {side} on node {node.id}", _with_node(spec, node.id, label_side=side)
        taken = {n.at for n in spec.nodes if n.id != node.id}
        for dc, dr in ((0, 0.5), (0, -0.5), (0.5, 0), (-0.5, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            at = (node.at[0] + dc, node.at[1] + dr)
            if at[0] < 0 or at[1] < 0 or any(abs(at[0] - t[0]) < 0.5 and abs(at[1] - t[1]) < 0.5 for t in taken):
                continue
            yield f"move node {node.id} to [{_fmt(at[0])}, {_fmt(at[1])}]", _with_node(spec, node.id, at=at)


def _fallback(o: Overlap) -> str:
    a = o.a
    if a.endswith(" label") and a.startswith("edge"):
        return f"shorten the label of {a[:-6]} (now {len(o.a_text)} chars) or add via waypoints so it runs elsewhere"
    if a.startswith("edge"):
        s, b = o.a_box, o.b_box
        if s.x2 - s.x1 < s.y2 - s.y1:  # vertical segment: shift it sideways past the box
            x = (s.x1 + s.x2) / 2
            to = b.x2 + 12 if b.x2 - x < x - b.x1 else b.x1 - 12
            return (f"move the vertical segment of {a} from x={round(x)} to x={round(to)} (clear of {o.b} {b.rounded()}): "
                    f"edit its via, or move the node it leaves from")
        y = (s.y1 + s.y2) / 2
        to = b.y2 + 12 if b.y2 - y < y - b.y1 else b.y1 - 12
        return (f"move the horizontal segment of {a} from y={round(y)} to y={round(to)} (clear of {o.b} {b.rounded()}): "
                f"edit its via, or move the node it leaves from")
    if a.startswith("node"):
        return f"move node {a.split()[1]} by half a cell (edit its at) or shorten its text"
    if a.startswith("zone") or o.b.startswith("zone"):
        return ("edit zones[*].cells: every element must sit fully inside or outside a zone "
                "(nodes belong inside, labels cannot sit on the border), and zones that touch "
                "must contain one another")
    return "move the rows of one band so they do not overlap (bands[*].rows)"


def suggest(spec: Spec, lay: Layout, o: Overlap, baseline: int) -> str:
    fixes: list[str] = []
    for element in (o.a, o.b):
        for desc, trial in _candidates(spec, lay, element):
            after = overlaps(layout(trial))
            if len(after) < baseline and not any({x.a, x.b} == {o.a, o.b} for x in after):
                fixes.append(desc)
                break
        if len(fixes) == 2:
            break
    return "; or ".join(fixes) if fixes else _fallback(o)


def _describe(name: str, box: Box, content: str) -> str:
    return f"{name}{f' {content!r}' if content else ''} {box.rounded()}"


# ------------------------------------------------------------------ check


def check(spec: Spec) -> list[Problem]:
    problems: list[Problem] = []
    ids = [n.id for n in spec.nodes]

    for p in (*spec.icons.packs, *spec.icons.monochrome):
        if p not in icons.packs():
            problems.append(Problem("unknown_pack", "icons", f"icon pack {p!r} does not exist",
                                    f"use one of: {', '.join(icons.packs())}"))
    order = tuple(p for p in spec.icons.packs if p in icons.packs())
    for n in spec.nodes:
        try:
            icons.resolve(n.icon, order)
        except icons.IconError as exc:
            problems.append(Problem(exc.kind, f"node {n.id} icon", f"node {n.id}: {exc.message}", exc.suggestion))
    for i, z in enumerate(spec.zones):
        if not z.badge:
            continue
        try:
            icons.resolve(z.badge, order)
        except icons.IconError as exc:
            problems.append(Problem(exc.kind, f"zone {i} badge", f"zone {i} badge: {exc.message}", exc.suggestion))

    for name, e in zip([f"edge {e.name}" for e in spec.edges], spec.edges):
        for end, ref in (("from", e.src), ("to", e.dst)):
            if ref not in ids:
                close = difflib.get_close_matches(ref, ids, n=3, cutoff=0.4)
                problems.append(Problem("bad_ref", name, f"{name}: {end} {ref!r} is not a node id",
                                        f"use one of: {', '.join(close or ids)}"))

    lay = layout(spec)
    for e in lay.edges:
        for v in e.edge.via:
            for nid, p in lay.nodes.items():
                if p.box.x1 < v[0] < p.box.x2 and p.box.y1 < v[1] < p.box.y2:
                    problems.append(Problem("bad_via", e.name, f"{e.name}: via point {list(v)} is inside node {nid} {p.box.rounded()}",
                                            f"move the waypoint outside node {nid}, e.g. [{round(v[0])}, {round(p.box.y2 + 12)}]"))

    found = overlaps(lay)
    for o in found:
        problems.append(Problem(
            "overlap", o.a,
            f"{_describe(o.a, o.a_box, o.a_text)} overlaps {_describe(o.b, o.b_box, o.b_text)} at {o.box.rounded()}",
            suggest(spec, lay, o, len(found)), o.b, tuple(o.box.rounded())))

    if spec.canvas:
        things: list[tuple[str, Box]] = [(f"node {i} icon", p.box) for i, p in lay.nodes.items()]
        things += [(t.name, t.box) for p in lay.nodes.values() for t in p.texts]
        things += [(e.label.name, e.label.box) for e in lay.edges if e.label]
        things += [(f"band {b.index}", b.box) for b in lay.bands]
        things += [(f"zone {z.index}", z.box) for z in lay.zones]
        things += [(z.label.name, z.label.box) for z in lay.zones if z.label]
        things += [(f"zone {z.index} badge", z.badge) for z in lay.zones if z.badge]
        for name, box in things:
            if not lay.view.contains(box):
                problems.append(Problem("out_of_canvas", name, f"{name} {box.rounded()} is outside canvas {lay.view.rounded()}",
                                        f"remove canvas to size it automatically, or set canvas to at least "
                                        f"[{round(max(lay.view.x2, box.x2) + 16)}, {round(max(lay.view.y2, box.y2) + 16)}]"))
    return problems


def blocking(problems: list[Problem], force: bool) -> list[Problem]:
    """Problems that stop a render; --force lets layout problems through, never broken references."""
    soft = {"overlap", "out_of_canvas"}
    return [p for p in problems if not (force and p.kind in soft)]
