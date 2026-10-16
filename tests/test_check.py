"""check() is the agent's feedback loop: every problem names both elements and offers a fix that works."""

from pathlib import Path

import pytest

from archdiagram.collide import check
from archdiagram.spec import load
from conftest import spec_from

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.yaml"))


def kinds(spec):
    return [p.kind for p in check(spec)]


def test_unknown_icon_suggests_the_closest_alias(empty_cache):
    [p] = check(spec_from("title: T\nnodes:\n  a: { icon: lamda, at: [0, 0] }\n"))
    assert p.kind == "unknown_icon" and p.element == "node a icon"
    assert "aws:lambda" in p.suggestion


def test_unknown_pack_prefix(empty_cache):
    [p] = check(spec_from("title: T\nnodes:\n  a: { icon: nope:lambda, at: [0, 0] }\n"))
    assert p.kind == "unknown_pack"


def test_bare_name_in_two_packs_is_ambiguous(cache):
    [p] = check(spec_from("title: T\nicons: { packs: [aws, brand] }\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"))
    assert p.kind == "ambiguous_icon" and "aws:lambda or brand:lambda" in p.suggestion


def test_raw_file_stem_resolves_once_fetched(cache):
    assert kinds(spec_from("title: T\nicons: { packs: [brand] }\nnodes:\n  a: { icon: notion, at: [0, 0] }\n")) == []


def test_bad_node_ref_lists_close_ids(empty_cache):
    [p] = check(spec_from("title: T\nnodes:\n  gatekeeper: { icon: lambda, at: [0, 0] }\n"
                          "edges:\n  - { from: gatekeper, to: gatekeeper }\n"))
    assert p.kind == "bad_ref" and "gatekeeper" in p.suggestion


def test_overlap_names_both_elements_and_a_fix_that_works(empty_cache):
    spec = spec_from("title: T\nnodes:\n"
                     "  a: { icon: lambda, at: [0, 0], label: a rather long service name }\n"
                     "  b: { icon: ddb, at: [1, 0], label: another long service name }\n")
    [p] = check(spec)
    assert (p.kind, p.element, p.with_) == ("overlap", "node a label", "node b label")
    assert p.box and "[" in p.message
    fix = p.suggestion.split(";")[0]
    assert fix.startswith(("set label_side", "move node"))


def test_edge_through_a_node_is_reported(empty_cache):
    spec = spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  m: { icon: ddb, at: [1, 0] }\n"
                     "  b: { icon: ddb, at: [2, 0] }\nedges:\n  - { from: a, to: b }\n")
    problems = check(spec)
    assert [(p.element, p.with_) for p in problems] == [("edge a->b", "node m icon")]


def test_clean_layout_passes(empty_cache):
    spec = spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0], label: A, sub: one }\n"
                     "  b: { icon: ddb, at: [1, 0], label: B, sub: two }\nedges:\n  - { from: a, to: b, label: x }\n")
    assert check(spec) == []


def test_out_of_canvas(empty_cache):
    spec = spec_from("title: T\ncanvas: [100, 100]\nnodes:\n  a: { icon: lambda, at: [1, 0] }\n")
    assert kinds(spec) == ["out_of_canvas"]


def test_node_on_a_zone_border_is_an_overlap(empty_cache):
    spec = spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                     "zones:\n  - { cells: [0.6, -1, 1, 0], label: VPC }\n")
    [p] = check(spec)
    assert (p.kind, p.element, p.with_) == ("overlap", "node a icon", "zone 0")


def test_nested_zones_do_not_overlap(empty_cache):
    spec = spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                     "zones:\n  - { cells: [0, 0, 1, 1], label: vpc }\n  - { cells: [0, 1, 1, 1], label: subnet }\n")
    assert check(spec) == []


def test_zones_that_partially_cross_are_an_overlap(empty_cache):
    spec = spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [4, 1] }\n"
                     "zones:\n  - { cells: [0, 0, 2, 0], label: a }\n  - { cells: [1, 0.5, 3, 1], label: b }\n")
    [p] = check(spec)
    assert (p.kind, p.element, p.with_) == ("overlap", "zone 0", "zone 1")


def test_zone_badge_is_resolved_like_a_node_icon(empty_cache):
    [p] = check(spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                          "zones:\n  - { cells: [0, 0, 0, 0], badge: no-such-badge }\n"))
    assert p.kind == "unknown_icon" and p.element == "zone 0 badge"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_examples_check_clean(empty_cache, path):
    assert check(load(path)) == []
