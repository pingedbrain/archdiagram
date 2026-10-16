"""Grid -> pixel coordinates, edge routing and text placement. Pure: no icons, no IO.

Every drawn thing gets a name ("node gk label", "edge lib->spend", "band 0 label") so the
collision report can point at it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .spec import Band, Edge, LegendItem, Node, Spec, Zone

GAP = 4             # px between an icon (or ring) and the end of an edge
RING = 8            # px the accent ring extends beyond the icon
LABEL_DY = 18       # icon bottom -> label baseline
SUB_DY = 15         # label baseline -> sub baseline
SIDE_DX = 8         # icon (or ring) edge -> side label anchor
EDGE_LABEL_DY = 9   # horizontal segment -> label baseline (above)
EDGE_LABEL_DX = 8   # vertical segment -> label anchor
MARGIN = 16
BAND_TOP = 40       # icon top of the first row -> band top
BAND_BOTTOM = 68    # icon bottom of the last row -> band bottom (clears label + sub)
BAND_PAD_X = 12
ZONE_TOP = 40       # icon top of the first row -> zone top (room for label + badge)
ZONE_BOTTOM = 68    # icon bottom of the last row -> zone bottom (clears label + sub)
ZONE_BADGE = 22     # badge icon size, top-left inside the zone
ZONE_BADGE_X = 12   # badge left offset from the zone border
HOP_CLEAR = 12      # no hop arc this close to a segment end
LEGEND_ROW = 20     # px per legend row
LEGEND_SW = 30      # swatch width inside the legend

# font sizes per text class, matching the stylesheet
SIZE = {"t": 14, "t mono": 12.5, "t gk-t": 16, "s": 11.5, "l": 11.5, "l acc-t": 11.5, "band-t": 11}
WIDTH = {"t mono": 0.62, "band-t": 0.64}  # chars * size * factor; default 0.56 (band text is letter-spaced)


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    def intersect(self, o: Box) -> Box | None:
        b = Box(max(self.x1, o.x1), max(self.y1, o.y1), min(self.x2, o.x2), min(self.y2, o.y2))
        return b if b.x2 > b.x1 and b.y2 > b.y1 else None

    def union(self, o: Box) -> Box:
        return Box(min(self.x1, o.x1), min(self.y1, o.y1), max(self.x2, o.x2), max(self.y2, o.y2))

    def contains(self, o: Box) -> bool:
        return self.x1 <= o.x1 and self.y1 <= o.y1 and o.x2 <= self.x2 and o.y2 <= self.y2

    def rounded(self) -> list[int]:
        return [round(self.x1), round(self.y1), round(self.x2), round(self.y2)]


@dataclass(frozen=True)
class Text:
    name: str
    content: str
    x: float
    y: float  # baseline
    anchor: str  # start | middle | end
    cls: str

    @property
    def box(self) -> Box:
        size = SIZE[self.cls]
        w = len(self.content) * size * WIDTH.get(self.cls, 0.56)
        x1 = {"start": self.x, "middle": self.x - w / 2, "end": self.x - w}[self.anchor]
        return Box(x1, self.y - size * 0.9, x1 + w, self.y + size * 0.3)


@dataclass(frozen=True)
class PlacedNode:
    node: Node
    cx: float
    cy: float
    size: float
    texts: tuple[Text, ...]

    @property
    def half(self) -> float:
        return self.size / 2 + (RING if self.node.accent else 0)

    @property
    def box(self) -> Box:
        h = self.half
        return Box(self.cx - h, self.cy - h, self.cx + h, self.cy + h)

    def extent(self, direction: str) -> float:
        """Distance from the centre to where an edge may touch, per side (bottom clears below-labels)."""
        if direction == "down" and self.texts and self.node.label_side == "below":
            return self.texts[-1].y - self.cy + 4
        return self.half


@dataclass(frozen=True)
class PlacedEdge:
    index: int
    edge: Edge
    name: str
    points: tuple[tuple[float, float], ...]
    label: Text | None


@dataclass(frozen=True)
class PlacedBand:
    index: int
    band: Band
    box: Box
    label: Text


@dataclass(frozen=True)
class PlacedZone:
    index: int
    zone: Zone
    box: Box
    label: Text | None
    badge: Box | None


@dataclass(frozen=True)
class PlacedLegendItem:
    index: int
    item: LegendItem
    swatch: Box
    label: Text


@dataclass(frozen=True)
class PlacedLegend:
    box: Box
    items: tuple[PlacedLegendItem, ...]


@dataclass(frozen=True)
class Layout:
    nodes: dict[str, PlacedNode]
    edges: tuple[PlacedEdge, ...]
    bands: tuple[PlacedBand, ...]
    zones: tuple[PlacedZone, ...]
    legend: PlacedLegend | None
    view: Box


def center(spec: Spec, at: tuple[float, float]) -> tuple[float, float]:
    g = spec.grid
    return g.origin[0] + at[0] * g.col, g.origin[1] + at[1] * g.row


def place_node(spec: Spec, n: Node) -> PlacedNode:
    cx, cy = center(spec, n.at)
    size = n.size or spec.grid.icon
    half = size / 2 + (RING if n.accent else 0)
    y = cy + size / 2 + LABEL_DY + (RING if n.accent else 0)
    x, anchor = {"below": (cx, "middle"), "left": (cx - half - SIDE_DX, "end"), "right": (cx + half + SIDE_DX, "start")}[n.label_side]
    texts = []
    if n.label:
        cls = "t gk-t" if n.accent else "t mono" if n.mono else "t"
        texts.append(Text(f"node {n.id} label", n.label, x, y, anchor, cls))
    if n.sub:
        texts.append(Text(f"node {n.id} sub", n.sub, x, y + SUB_DY if n.label else y, anchor, "s"))
    return PlacedNode(n, cx, cy, size, tuple(texts))


def _toward(a: float, b: float) -> int:
    return 1 if b >= a else -1


def _exit(p: PlacedNode, w: tuple[float, float]) -> list[tuple[float, float]]:
    """Points from node p's border toward waypoint w, leaving orthogonally (an elbow if needed)."""
    wx, wy = w
    in_x, in_y = abs(wx - p.cx) <= p.half, abs(wy - p.cy) <= p.half
    if in_x and not in_y:
        s = _toward(p.cy, wy)
        return [(wx, p.cy + s * (p.extent("down" if s > 0 else "up") + GAP))]
    if in_y and not in_x:
        s = _toward(p.cx, wx)
        return [(p.cx + s * (p.half + GAP), wy)]
    s = _toward(p.cx, wx)  # neither: leave horizontally from the centre line, then turn
    return [(p.cx + s * (p.half + GAP), p.cy), (wx, p.cy)]


def route(spec: Spec, e: Edge, a: PlacedNode, b: PlacedNode) -> tuple[tuple[float, float], ...]:
    if e.via:
        mids = list(e.via)
    elif abs(a.cy - b.cy) < 0.5 or abs(a.cx - b.cx) < 0.5:
        mids = []
    elif e.route == "vh":
        mids = [(a.cx, b.cy)]
    else:  # auto (not aligned) and hv
        mids = [(b.cx, a.cy)]
    if not mids:
        if abs(a.cy - b.cy) < 0.5:
            s = _toward(a.cx, b.cx)
            return ((a.cx + s * (a.half + GAP), a.cy), (b.cx - s * (b.half + GAP), b.cy))
        s = _toward(a.cy, b.cy)
        down, up = ("down", "up") if s > 0 else ("up", "down")
        return ((a.cx, a.cy + s * (a.extent(down) + GAP)), (b.cx, b.cy - s * (b.extent(up) + GAP)))
    start = _exit(a, mids[0])
    end = list(reversed(_exit(b, mids[-1])))
    pts = start + mids + end
    out: list[tuple[float, float]] = []
    for p in pts:  # drop duplicates and collinear middles so labels land on real segments
        if out and abs(out[-1][0] - p[0]) < 0.01 and abs(out[-1][1] - p[1]) < 0.01:
            continue
        if len(out) >= 2 and _collinear(out[-2], out[-1], p):
            out[-1] = p
            continue
        out.append(p)
    return tuple(out)


def _collinear(p, q, r) -> bool:
    return (abs(p[0] - q[0]) < 0.01 and abs(q[0] - r[0]) < 0.01) or (abs(p[1] - q[1]) < 0.01 and abs(q[1] - r[1]) < 0.01)


def segments(points) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(points, points[1:]))


def edge_label(name: str, e: Edge, points) -> Text | None:
    if not e.label:
        return None
    segs = segments(points)
    vertical = [s for s in segs if abs(s[0][0] - s[1][0]) < 0.01]
    horizontal = [s for s in segs if s not in vertical]
    pool = {"left": vertical, "right": vertical, "above": horizontal, "below": horizontal}.get(e.label_side or "", []) or segs
    (x1, y1), (x2, y2) = max(pool, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    cls = "l acc-t" if e.accent else "l"
    if abs(x1 - x2) < 0.01:
        if e.label_side == "left":
            return Text(name, e.label, mx - EDGE_LABEL_DX, my + 4, "end", cls)
        return Text(name, e.label, mx + EDGE_LABEL_DX, my + 4, "start", cls)
    if e.label_side == "below":
        return Text(name, e.label, mx, my + EDGE_LABEL_DY + SIZE[cls] * 0.8, "middle", cls)
    return Text(name, e.label, mx, my - EDGE_LABEL_DY, "middle", cls)


def edge_names(spec: Spec) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for e in spec.edges:
        seen[e.name] = seen.get(e.name, 0) + 1
        out.append(f"edge {e.name}" + (f"#{seen[e.name]}" if seen[e.name] > 1 else ""))
    return out


def points_box(points) -> Box:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return Box(min(xs), min(ys), max(xs), max(ys))


def crossings(edges: list[PlacedEdge] | tuple[PlacedEdge, ...]) -> dict[int, dict[int, list[tuple[float, float]]]]:
    """Hop spots: {edge_index: {segment_index: [(x, y)]}} — a vertical segment crossing another
    edge's horizontal wire gets a small jump arc at each crossing (the circuit-diagram convention)."""
    out: dict[int, dict[int, list[tuple[float, float]]]] = {}
    for e in edges:
        vsegs = [(k, s) for k, s in enumerate(segments(e.points)) if abs(s[0][0] - s[1][0]) < 0.01]
        if not vsegs:
            continue
        for f in edges:
            if f is e or e.edge.src == f.edge.src or e.edge.dst == f.edge.dst:
                continue  # forks and merges share their trunk on purpose
            for p, q in segments(f.points):
                if abs(p[1] - q[1]) > 0.01:
                    continue
                hx1, hx2, hy = min(p[0], q[0]), max(p[0], q[0]), p[1]
                for k, (a, b) in vsegs:
                    lo, hi = sorted((a[1], b[1]))
                    if hx1 < a[0] < hx2 and lo + HOP_CLEAR < hy < hi - HOP_CLEAR:
                        out.setdefault(e.index, {}).setdefault(k, []).append((a[0], hy))
    return out


def layout(spec: Spec) -> Layout:
    nodes = {n.id: place_node(spec, n) for n in spec.nodes}
    edges = []
    for i, (e, name) in enumerate(zip(spec.edges, edge_names(spec))):
        a, b = nodes.get(e.src), nodes.get(e.dst)
        if a is None or b is None:  # bad_ref is reported by check; nothing to draw
            continue
        pts = route(spec, e, a, b)
        edges.append(PlacedEdge(i, e, name, pts, edge_label(f"{name} label", e, pts)))

    half = spec.grid.icon / 2
    zones = []
    for i, zone in enumerate(spec.zones):
        c1, r1, c2, r2 = zone.cells
        box = Box(center(spec, (c1, 0))[0] - spec.grid.col / 2, center(spec, (0, r1))[1] - half - ZONE_TOP,
                  center(spec, (c2, 0))[0] + spec.grid.col / 2, center(spec, (0, r2))[1] + half + ZONE_BOTTOM)
        badge = (Box(box.x1 + ZONE_BADGE_X, box.y1 + 8, box.x1 + ZONE_BADGE_X + ZONE_BADGE,
                     box.y1 + 8 + ZONE_BADGE) if zone.badge else None)
        label = None
        if zone.label:
            lx = box.x1 + (ZONE_BADGE_X + ZONE_BADGE + 8 if badge else 16)
            label = Text(f"zone {i} label", zone.label, lx, box.y1 + 24, "start", "band-t")
        zones.append(PlacedZone(i, zone, box, label, badge))

    boxes = [p.box for p in nodes.values()] + [t.box for p in nodes.values() for t in p.texts]
    boxes += [points_box(e.points) for e in edges] + [e.label.box for e in edges if e.label]
    boxes += [z.box for z in zones] + [z.label.box for z in zones if z.label]
    boxes += [z.badge for z in zones if z.badge]
    content = boxes[0]
    for b in boxes[1:]:
        content = content.union(b)

    bands = []
    for i, band in enumerate(spec.bands):
        top = center(spec, (0, band.rows[0]))[1] - half - BAND_TOP
        bottom = center(spec, (0, band.rows[1]))[1] + half + BAND_BOTTOM
        box = Box(content.x1 - BAND_PAD_X, top, content.x2 + BAND_PAD_X, bottom)
        bands.append(PlacedBand(i, band, box, Text(f"band {i} label", band.label, box.x1 + 16, top + 22, "start", "band-t")))

    bands_box = None
    for b in bands:
        bands_box = b.box if bands_box is None else bands_box.union(b.box)

    legend = None
    if spec.legend:
        bottom = max(content.y2, bands_box.y2 if bands_box else content.y2)
        text_w = max(len(it.text) for it in spec.legend) * SIZE["l"] * 0.56
        w = 14 + LEGEND_SW + 10 + text_w + 14
        top = bottom + 20
        items = []
        for i, it in enumerate(spec.legend):
            sy = top + 10 + i * LEGEND_ROW
            swatch = Box(content.x1 + 14, sy + 3, content.x1 + 14 + LEGEND_SW, sy + 3 + 14)
            items.append(PlacedLegendItem(
                i, it, swatch, Text(f"legend {i} label", it.text, swatch.x2 + 10, sy + 14, "start", "l")))
        legend = PlacedLegend(Box(content.x1, top, content.x1 + w, top + 10 + LEGEND_ROW * len(items) + 6),
                              tuple(items))

    if spec.canvas:
        view = Box(0, 0, spec.canvas[0], spec.canvas[1])
    else:
        everything = content
        for b in bands:
            everything = everything.union(b.box).union(b.label.box)
        if legend:
            everything = everything.union(legend.box)
        view = Box(math.floor(everything.x1 - MARGIN), math.floor(everything.y1 - MARGIN),
                   math.ceil(everything.x2 + MARGIN), math.ceil(everything.y2 + MARGIN))
    return Layout(nodes, tuple(edges), tuple(bands), tuple(zones), legend, view)
