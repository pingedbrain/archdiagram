"""Load a diagram spec from YAML into frozen dataclasses.

Structural errors (bad YAML, wrong types, unknown keys, missing fields) raise SpecError with
every problem found, each prefixed by its path in the document (e.g. `nodes.gk.at`). Semantic
problems that need the whole picture (unknown icons, edges to missing nodes, overlaps) are not
raised here: `collide.check` reports them as structured problems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

LabelSide = Literal["below", "left", "right"]
EdgeLabelSide = Literal["above", "below", "left", "right"]
Route = Literal["auto", "hv", "vh"]
BandStyle = Literal["solid", "dashed"]
ZoneStyle = Literal["solid", "dashed", "dotted"]
TINTS = ("orange", "green", "blue", "purple", "gray", "red")
SAMPLES = ("edge", "accent", "dashed", "dots", "ants", "zone", "zone-dotted")


class SpecError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Grid:
    col: float = 150
    row: float = 110
    origin: tuple[float, float] = (80, 70)
    icon: float = 44


@dataclass(frozen=True)
class Icons:
    packs: tuple[str, ...] = ("aws", "generic")
    monochrome: tuple[str, ...] = ()


@dataclass(frozen=True)
class Band:
    label: str
    rows: tuple[float, float]
    style: BandStyle = "solid"


@dataclass(frozen=True)
class Zone:
    cells: tuple[float, float, float, float]
    label: str = ""
    style: ZoneStyle = "dashed"
    badge: str = ""
    tint: str = ""
    label_side: str = "top"  # "top" | "bottom" — inside corner for the zone label


@dataclass(frozen=True)
class LegendItem:
    text: str
    sample: str = ""  # a line/zone swatch from SAMPLES; "" when `icon` is used
    icon: str = ""
    tint: str = ""


@dataclass(frozen=True)
class Node:
    id: str
    icon: str
    at: tuple[float, float] | None = None
    label: str = ""
    sub: str = ""
    note: str = ""
    accent: bool = False
    size: float | None = None
    label_side: LabelSide = "below"
    mono: bool = False


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    label: str = ""
    route: Route = "auto"
    via: tuple[tuple[float, float], ...] = ()
    accent: bool = False
    flow: str = ""  # "" | "dots" | "ants"
    dashed: bool = False
    both: bool = False
    arrow: str = "filled"  # "filled" | "open" | "diamond"
    num: bool = False
    label_side: EdgeLabelSide | None = None

    @property
    def name(self) -> str:
        return f"{self.src}->{self.dst}"


@dataclass(frozen=True)
class Spec:
    title: str
    nodes: tuple[Node, ...]
    claim: str = ""
    caption: str = ""
    icons: Icons = field(default_factory=Icons)
    grid: Grid = field(default_factory=Grid)
    bands: tuple[Band, ...] = ()
    zones: tuple[Zone, ...] = ()
    legend: tuple[LegendItem, ...] = ()
    edges: tuple[Edge, ...] = ()
    canvas: tuple[float, float] | None = None
    prefix: str = ""

    @property
    def id_prefix(self) -> str:
        if self.prefix:
            return self.prefix
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-") or "diagram"
        return slug if slug[0].isalpha() else f"d-{slug}"

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)


class _Reader:
    """Collects every structural error instead of stopping at the first one."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def fail(self, path: str, msg: str) -> None:
        self.errors.append(f"{path}: {msg}")

    def keys(self, path: str, obj: Any, allowed: set[str], required: set[str] = frozenset()) -> bool:
        if not isinstance(obj, dict):
            self.fail(path, f"expected a mapping, got {type(obj).__name__}")
            return False
        for k in obj:
            if k not in allowed:
                self.fail(f"{path}.{k}", f"unknown key; allowed: {', '.join(sorted(allowed))}")
        for k in sorted(required - set(obj)):
            self.fail(f"{path}.{k}", "required")
        return True

    def text(self, path: str, v: Any, default: str = "") -> str:
        if v is None:
            return default
        if isinstance(v, bool):
            self.fail(path, f"YAML read this as boolean {v}; quote it, e.g. \"{'on' if v else 'off'}\"")
            return default
        if isinstance(v, (int, float)):
            return str(v)
        if not isinstance(v, str):
            self.fail(path, f"expected text, got {type(v).__name__}")
            return default
        return v

    def num(self, path: str, v: Any, default: float = 0) -> float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            self.fail(path, f"expected a number, got {v!r}")
            return default
        return v

    def pair(self, path: str, v: Any, what: str = "[x, y]") -> tuple[float, float]:
        if not isinstance(v, (list, tuple)) or len(v) != 2:
            self.fail(path, f"expected a {what} pair, got {v!r}")
            return (0, 0)
        return (self.num(f"{path}[0]", v[0]), self.num(f"{path}[1]", v[1]))

    def flag(self, path: str, v: Any) -> bool:
        if v is None:
            return False
        if not isinstance(v, bool):
            self.fail(path, f"expected true or false, got {v!r}")
            return False
        return v

    def choice(self, path: str, v: Any, options: tuple[str, ...], default: str | None) -> Any:
        if v is None:
            return default
        if v not in options:
            self.fail(path, f"expected one of {', '.join(options)}, got {v!r}")
            return default
        return v

    def names(self, path: str, v: Any, default: tuple[str, ...]) -> tuple[str, ...]:
        if v is None:
            return default
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            self.fail(path, f"expected a list of names, got {v!r}")
            return default
        return tuple(v)


def parse(doc: Any) -> Spec:
    r = _Reader()
    top = {"title", "claim", "caption", "icons", "grid", "bands", "zones", "legend", "nodes", "edges", "canvas", "prefix"}
    if not r.keys("spec", doc, top, {"title", "nodes"}):
        raise SpecError(r.errors)

    icons = Icons()
    if doc.get("icons") is not None and r.keys("icons", doc["icons"], {"packs", "monochrome"}):
        i = doc["icons"]
        icons = Icons(
            packs=r.names("icons.packs", i.get("packs"), Icons.packs),
            monochrome=r.names("icons.monochrome", i.get("monochrome"), ()),
        )

    grid = Grid()
    if doc.get("grid") is not None and r.keys("grid", doc["grid"], {"col", "row", "origin", "icon"}):
        g = doc["grid"]
        grid = Grid(
            col=r.num("grid.col", g.get("col", Grid.col)),
            row=r.num("grid.row", g.get("row", Grid.row)),
            origin=r.pair("grid.origin", g.get("origin", list(Grid.origin))),
            icon=r.num("grid.icon", g.get("icon", Grid.icon)),
        )

    bands = []
    raw_bands = doc.get("bands") or []
    if not isinstance(raw_bands, list):
        r.fail("bands", "expected a list")
        raw_bands = []
    for i, b in enumerate(raw_bands):
        p = f"bands[{i}]"
        if not r.keys(p, b, {"label", "rows", "style"}, {"label", "rows"}):
            continue
        rows = r.pair(f"{p}.rows", b.get("rows"), "[first_row, last_row]")
        if rows[0] > rows[1]:
            r.fail(f"{p}.rows", f"first row {rows[0]} is after last row {rows[1]}")
        bands.append(Band(r.text(f"{p}.label", b.get("label")), rows, r.choice(f"{p}.style", b.get("style"), ("solid", "dashed"), "solid")))

    zones = []
    raw_zones = doc.get("zones") or []
    if not isinstance(raw_zones, list):
        r.fail("zones", "expected a list")
        raw_zones = []
    for i, z in enumerate(raw_zones):
        p = f"zones[{i}]"
        if not r.keys(p, z, {"label", "cells", "style", "badge", "tint", "label_side"}, {"cells"}):
            continue
        cells = z.get("cells")
        if not isinstance(cells, (list, tuple)) or len(cells) != 4:
            r.fail(f"{p}.cells", f"expected a [col1, row1, col2, row2] quadruple, got {cells!r}")
            cells = (0, 0, 0, 0)
        cells = tuple(r.num(f"{p}.cells[{j}]", v) for j, v in enumerate(cells))
        if cells[0] > cells[2] or cells[1] > cells[3]:
            r.fail(f"{p}.cells", f"first cell {cells[:2]} is past last cell {cells[2:]}")
        zones.append(Zone(
            cells,
            label=r.text(f"{p}.label", z.get("label")),
            style=r.choice(f"{p}.style", z.get("style"), ("solid", "dashed", "dotted"), "dashed"),
            badge=r.text(f"{p}.badge", z.get("badge")),
            tint=r.choice(f"{p}.tint", z.get("tint"), TINTS, ""),
            label_side=r.choice(f"{p}.label_side", z.get("label_side"), ("top", "bottom"), "top"),
        ))

    legend = []
    raw_legend = doc.get("legend") or []
    if not isinstance(raw_legend, list):
        r.fail("legend", "expected a list")
        raw_legend = []
    for i, it in enumerate(raw_legend):
        p = f"legend[{i}]"
        if not r.keys(p, it, {"sample", "icon", "text", "tint"}, {"text"}):
            continue
        if (it.get("sample") is None) == (it.get("icon") is None):
            r.fail(p, "give exactly one of sample or icon")
            continue
        legend.append(LegendItem(
            text=r.text(f"{p}.text", it.get("text")),
            sample=r.choice(f"{p}.sample", it.get("sample"), SAMPLES, ""),
            icon=r.text(f"{p}.icon", it.get("icon")),
            tint=r.choice(f"{p}.tint", it.get("tint"), TINTS, ""),
        ))

    nodes = []
    raw_nodes = doc.get("nodes")
    if not isinstance(raw_nodes, dict) or not raw_nodes:
        r.fail("nodes", "expected a non-empty mapping of node id -> node")
        raw_nodes = {}
    node_keys = {"icon", "at", "label", "sub", "note", "accent", "size", "label_side", "mono"}
    n_at = sum(1 for n in raw_nodes.values() if isinstance(n, dict) and "at" in n)
    if n_at and n_at != len(raw_nodes):
        r.fail("nodes", "give at for every node or for none (empty at means automatic layout)")
    for nid, n in raw_nodes.items():
        p = f"nodes.{nid}"
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", str(nid)):
            r.fail(p, "node id must match [A-Za-z_][A-Za-z0-9_-]*")
        if not r.keys(p, n, node_keys, {"icon"}):
            continue
        size = n.get("size")
        nodes.append(Node(
            id=str(nid),
            icon=r.text(f"{p}.icon", n.get("icon")),
            at=r.pair(f"{p}.at", n["at"], "[col, row]") if "at" in n else None,
            label=r.text(f"{p}.label", n.get("label")),
            sub=r.text(f"{p}.sub", n.get("sub")),
            note=r.text(f"{p}.note", n.get("note")),
            accent=r.flag(f"{p}.accent", n.get("accent")),
            size=None if size is None else r.num(f"{p}.size", size),
            label_side=r.choice(f"{p}.label_side", n.get("label_side"), ("below", "left", "right"), "below"),
            mono=r.flag(f"{p}.mono", n.get("mono")),
        ))

    edges = []
    raw_edges = doc.get("edges") or []
    if not isinstance(raw_edges, list):
        r.fail("edges", "expected a list")
        raw_edges = []
    edge_keys = {"from", "to", "label", "route", "via", "accent", "flow", "dashed", "both", "arrow", "num", "label_side"}
    for i, e in enumerate(raw_edges):
        p = f"edges[{i}]"
        if not r.keys(p, e, edge_keys, {"from", "to"}):
            continue
        via = e.get("via") or []
        if not isinstance(via, list):
            r.fail(f"{p}.via", "expected a list of [x, y] pixel points")
            via = []
        fv = e.get("flow")
        if fv is None or fv is False:
            flow = ""
        elif fv is True or fv in ("dots", "ants"):
            flow = "dots" if fv is True else fv
        else:
            r.fail(f"{p}.flow", f"expected true, dots or ants, got {fv!r}")
            flow = ""
        edges.append(Edge(
            src=r.text(f"{p}.from", e.get("from")),
            dst=r.text(f"{p}.to", e.get("to")),
            label=r.text(f"{p}.label", e.get("label")),
            route=r.choice(f"{p}.route", e.get("route"), ("auto", "hv", "vh"), "auto"),
            via=tuple(r.pair(f"{p}.via[{j}]", v) for j, v in enumerate(via)),
            accent=r.flag(f"{p}.accent", e.get("accent")),
            flow=flow,
            dashed=r.flag(f"{p}.dashed", e.get("dashed")),
            both=r.flag(f"{p}.both", e.get("both")),
            arrow=r.choice(f"{p}.arrow", e.get("arrow"), ("filled", "open", "diamond"), "filled"),
            num=r.flag(f"{p}.num", e.get("num")),
            label_side=r.choice(f"{p}.label_side", e.get("label_side"), ("above", "below", "left", "right"), None),
        ))

    canvas = None
    if doc.get("canvas") is not None:
        canvas = r.pair("canvas", doc["canvas"], "[width, height]")

    prefix = r.text("prefix", doc.get("prefix"))
    if prefix and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", prefix):
        r.fail("prefix", "must match [A-Za-z][A-Za-z0-9_-]* (it becomes an SVG id prefix)")

    if r.errors:
        raise SpecError(r.errors)
    return Spec(
        title=r.text("title", doc.get("title")),
        claim=r.text("claim", doc.get("claim")),
        caption=r.text("caption", doc.get("caption")),
        icons=icons, grid=grid, bands=tuple(bands), zones=tuple(zones), legend=tuple(legend),
        nodes=tuple(nodes), edges=tuple(edges),
        canvas=canvas, prefix=prefix,
    )


def load(path: str | Path) -> Spec:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecError([f"{path}: cannot read ({exc.strerror})"]) from exc
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError([f"{path}: invalid YAML: {exc}"]) from exc
    return parse(doc)
