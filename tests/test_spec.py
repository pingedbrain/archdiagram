"""Structural errors are reported all at once, each with its path, so an agent can fix them in one pass."""

import pytest

from archdiagram.spec import SpecError
from conftest import spec_from


def errors(text: str) -> list[str]:
    with pytest.raises(SpecError) as exc:
        spec_from(text)
    return exc.value.errors


def test_missing_at_names_the_node():
    assert "nodes.gk.at: required" in errors("title: T\nnodes:\n  gk: { icon: lambda }\n")


def test_unknown_key_lists_allowed_keys():
    errs = errors("title: T\nnodes:\n  gk: { icon: lambda, at: [0, 0], lable: x }\n")
    assert errs[0].startswith("nodes.gk.lable: unknown key; allowed:")


def test_yaml_boolean_label_asks_for_quotes():
    errs = errors("title: T\nnodes:\n  s: { icon: ddb, at: [0, 0], label: off }\n")
    assert "quote it" in errs[0]


def test_every_error_is_reported_not_just_the_first():
    errs = errors("title: T\nnodes:\n  a: { icon: x }\n  b: { at: [1, 1] }\nedges:\n  - { from: a }\n")
    assert {"nodes.a.at: required", "nodes.b.icon: required", "edges[0].to: required"} <= set(errs)


def test_defaults_and_prefix_slug():
    spec = spec_from("title: Agent Platform!\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n")
    assert spec.grid.col == 150 and spec.grid.row == 110 and spec.grid.origin == (80, 70) and spec.grid.icon == 44
    assert spec.icons.packs == ("aws", "generic")
    assert spec.id_prefix == "agent-platform"


def test_zone_cells_must_be_a_quadruple_in_order():
    errs = errors("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\nzones:\n  - { cells: [0, 0, 1] }\n")
    assert errs[0].startswith("zones[0].cells: expected a [col1, row1, col2, row2] quadruple")
    errs = errors("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\nzones:\n  - { cells: [1, 0, 0, 1] }\n")
    assert "is past last cell" in errs[0]


def test_zone_defaults_and_badge():
    spec = spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                     "zones:\n  - { cells: [0, 0, 1, 1], label: VPC, badge: aws:group-vpc }\n")
    z = spec.zones[0]
    assert z.cells == (0, 0, 1, 1) and z.style == "dashed" and z.label == "VPC" and z.badge == "aws:group-vpc"
    errs = errors("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\nzones:\n  - { cells: [0, 0, 1, 1], style: funky }\n")
    assert errs[0].startswith("zones[0].style: expected one of solid, dashed, dotted")


def test_edge_flow_styles_and_flags():
    spec = spec_from("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [1, 0] }\n"
                     "edges:\n  - { from: a, to: b, flow: ants }\n  - { from: b, to: a, flow: true, dashed: true, both: true }\n")
    assert spec.edges[0].flow == "ants"
    e = spec.edges[1]
    assert e.flow == "dots" and e.dashed and e.both
    errs = errors("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [1, 0] }\n"
                  "edges:\n  - { from: a, to: b, flow: fast }\n")
    assert errs[0].startswith("edges[0].flow: expected true, dots or ants")
