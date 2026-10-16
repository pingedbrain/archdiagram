"""Grid maths and routing: these numbers are what makes figures line up like the hand-made ones."""

from archdiagram.layout import GAP, layout
from conftest import spec_from

BASE = "title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"


def test_node_center_is_origin_plus_at_times_grid():
    lay = layout(spec_from("title: T\ngrid: { col: 100, row: 50, origin: [10, 20] }\nnodes:\n  a: { icon: lambda, at: [3.5, 2] }\n"))
    assert (lay.nodes["a"].cx, lay.nodes["a"].cy) == (360, 120)


def test_label_and_sub_sit_below_the_icon():
    lay = layout(spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0], label: L, sub: S }\n"))
    label, sub = lay.nodes["a"].texts
    assert (label.x, label.y, label.anchor) == (80, 70 + 22 + 18, "middle")
    assert sub.y == label.y + 15


def test_auto_route_is_straight_when_aligned_and_ends_at_icon_edges():
    lay = layout(spec_from(BASE + "  b: { icon: ddb, at: [1, 0] }\nedges:\n  - { from: a, to: b }\n"))
    assert lay.edges[0].points == ((80 + 22 + GAP, 70), (230 - 22 - GAP, 70))


def test_auto_route_elbows_horizontal_then_vertical():
    lay = layout(spec_from(BASE + "  b: { icon: ddb, at: [1, 1] }\nedges:\n  - { from: a, to: b }\n"))
    assert lay.edges[0].points == ((106, 70), (230, 70), (230, 180 - 22 - GAP))


def test_vh_route_goes_vertical_first_and_clears_the_labels_below():
    lay = layout(spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0], label: L }\n"
                           "  b: { icon: ddb, at: [1, 1] }\nedges:\n  - { from: a, to: b, route: vh }\n"))
    start = lay.edges[0].points[0]
    assert start[0] == 80 and start[1] == 70 + 22 + 18 + 4 + GAP  # below the label baseline, not the icon


def test_accent_ring_moves_the_endpoint_out():
    lay = layout(spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0], accent: true }\n"
                           "  b: { icon: ddb, at: [1, 0] }\nedges:\n  - { from: a, to: b }\n"))
    assert lay.edges[0].points[0] == (80 + 22 + 8 + GAP, 70)


def test_via_waypoint_exits_on_the_matching_side():
    lay = layout(spec_from(BASE + "  b: { icon: ddb, at: [1, -0.6] }\nedges:\n  - { from: a, to: b, via: [[90, 0]] }\n"))
    assert lay.edges[0].points == ((90, 70 - 22 - GAP), (90, 0), (230 - 22 - GAP, 0))


def test_edge_label_above_longest_horizontal_segment():
    lay = layout(spec_from(BASE + "  b: { icon: ddb, at: [1, 0] }\nedges:\n  - { from: a, to: b, label: x }\n"))
    label = lay.edges[0].label
    assert (label.x, label.y, label.anchor) == (155, 61, "middle")


def test_zone_box_spans_whole_columns_and_clears_labels_below():
    lay = layout(spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [1, 0] }\n"
                           "zones:\n  - { cells: [0, 0, 1, 0], label: VPC }\n"))
    z = lay.zones[0]
    assert (z.box.x1, z.box.x2) == (80 - 75, 230 + 75)  # borders at the cell edges
    assert (z.box.y1, z.box.y2) == (70 - 22 - 40, 70 + 22 + 68)  # band-style room for label + sub
    assert (z.label.x, z.label.y, z.label.cls) == (z.box.x1 + 16, z.box.y1 + 24, "band-t")


def test_zone_badge_sits_in_the_corner_and_pushes_the_label():
    lay = layout(spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                           "zones:\n  - { cells: [0, 0, 0, 0], label: VPC, badge: aws:group-vpc }\n"))
    z = lay.zones[0]
    assert (z.badge.x1, z.badge.y1) == (z.box.x1 + 12, z.box.y1 + 8) and z.badge.x2 - z.badge.x1 == 22
    assert z.label.x == z.box.x1 + 12 + 22 + 8


def test_crossings_gives_a_hop_spot_on_the_vertical_wire():
    from archdiagram.layout import crossings
    lay = layout(spec_from("title: T\nnodes:\n"
                           "  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [2, 0] }\n"
                           "  c: { icon: lambda, at: [1, -1] }\n  d: { icon: ddb, at: [1, 1] }\n"
                           "edges:\n  - { from: a, to: b }\n  - { from: c, to: d }\n"))
    assert crossings(lay.edges) == {1: {0: [(230.0, 70.0)]}}  # c->d hops the a->b wire


def test_legend_sits_below_the_content():
    lay = layout(spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                           "legend:\n  - { sample: accent, text: crit }\n  - { icon: lambda, text: fn }\n"))
    lg = lay.legend
    assert lg.box.y1 > lay.nodes["a"].box.y2 and len(lg.items) == 2
    assert lg.items[1].label.x == lg.items[1].swatch.x2 + 10
