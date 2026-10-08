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
