"""Output invariants: ids never collide between figures on one page, and only used icons ship."""

import re

import pytest

from archdiagram import icons
from archdiagram.layout import layout
from archdiagram.render import css, fragment, standalone_svg
from conftest import FIX, make_zip, spec_from

TWO = ("title: {title}\nnodes:\n  a: {{ icon: lambda, at: [0, 0], accent: true }}\n"
       "  b: {{ icon: generic:users, at: [1, 0] }}\nedges:\n  - {{ from: a, to: b, accent: true }}\n")


def render(text: str) -> str:
    spec = spec_from(text)
    return fragment(spec, layout(spec))


def test_two_prefixes_never_share_an_id(cache):
    page = render(TWO.format(title="First")) + render(TWO.format(title="Second"))
    ids = re.findall(r'\sid="([^"]+)"', page)
    assert len(ids) == len(set(ids)) and len(ids) > 4
    for ref in re.findall(r'(?:href="#|url\(#)([^")]+)', page):
        assert ref in ids  # every reference still points at an existing id


def test_only_used_icons_are_embedded(cache):
    out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: lambda, at: [1, 0] }\n")
    assert re.findall(r'<symbol id="([^"]+)"', out) == ["t-aws-lambda"]


def test_generic_ink_becomes_current_color_and_gets_a_tile(cache):
    out = render("title: T\nnodes:\n  a: { icon: generic:users, at: [0, 0] }\n")
    assert "currentColor" in out and "#232F3D" not in out
    assert '<rect class="tile"' in out and '<g class="ink">' in out


def test_embedded_css_classes_are_inlined(cache):
    out = render("title: T\nnodes:\n  a: { icon: apigw, at: [0, 0] }\n")
    symbol = re.search(r"<symbol.*?</symbol>", out).group(0)
    assert "<style" not in symbol and "class=" not in symbol
    assert 'style="fill: #4285f4;"' in symbol and 'style="fill: none;fill: #4285f4;opacity:.5"' in symbol


def test_brand_uses_official_hex_unless_too_dark_or_monochrome(cache):
    out = render("title: T\nicons: { packs: [brand] }\nnodes:\n  a: { icon: jira, at: [0, 0] }\n  b: { icon: notion, at: [1, 0] }\n")
    assert '<g fill="#0052CC">' in out and '<g fill="currentColor">' in out
    mono = render("title: T\nicons: { packs: [brand], monochrome: [brand] }\nnodes:\n  a: { icon: jira, at: [0, 0] }\n")
    assert "#0052CC" not in mono


def test_missing_pack_is_an_actionable_error(empty_cache):
    with pytest.raises(icons.IconError) as exc:
        render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n")
    assert exc.value.kind == "icons_missing" and "icons fetch aws" in exc.value.suggestion


def test_standalone_svg_carries_its_own_tokens(cache):
    spec = spec_from(TWO.format(title="T"))
    out = standalone_svg(spec, layout(spec))
    assert out.startswith('<svg xmlns="http://www.w3.org/2000/svg" class="arch"') and "prefers-color-scheme: dark" in out


def test_css_has_light_fallbacks():
    assert "var(--fg-3, #6B7588)" in css()


def test_fetch_skips_junk_and_escaping_members(cache):
    root = icons.pack_dir(icons.get_pack("aws"))
    assert not (root.parent / "escape.svg").exists() and not (root / "__MACOSX").exists()


def test_zone_draws_a_dashed_rect_with_a_corner_badge(cache):
    out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                 "zones:\n  - { cells: [0, 0, 0, 0], label: VPC, style: dashed, badge: lambda }\n")
    assert '<rect class="zone b2"' in out and re.search(r'<use href="#t-aws-lambda"[^>]*width="22"', out)
    assert '>VPC</text>' in out


def test_zone_dotted_and_solid_styles(cache):
    for style, cls in (("dotted", "zone b3"), ("solid", "zone")):
        out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n"
                     f"zones:\n  - {{ cells: [0, 0, 0, 0], style: {style} }}\n")
        assert f'<rect class="{cls}"' in out


def test_flow_edge_gets_an_id_and_travelling_packets(cache):
    out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [1, 0] }\n"
                 "edges:\n  - { from: a, to: b, flow: true }\n")
    assert '<path id="t-e0"' in out and '<animateMotion' in out and 'href="#t-e0"' in out
    assert out.count('class="pkt"') == 1 and "<line" not in out


def test_long_flow_edge_spreads_packets_and_combines_with_accent(cache):
    out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [5, 0] }\n"
                 "edges:\n  - { from: a, to: b, flow: true, accent: true }\n")
    assert out.count('class="pkt acc"') == 4  # ~700 px at one packet per 160 px
    assert 'prefers-reduced-motion' not in out  # that rule lives in the stylesheet


def test_flow_ants_uses_css_marching_dashes(cache):
    out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [1, 1] }\n"
                 "edges:\n  - { from: a, to: b, flow: ants }\n")
    assert 'class="a ants"' in out and "animateMotion" not in out
    assert "@keyframes arch-ants" in css()


def test_dashed_and_both_endpoints(cache):
    out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [1, 0] }\n"
                 "edges:\n  - { from: a, to: b, dashed: true, both: true }\n")
    assert 'class="a dash"' in out and "marker-start" in out and "marker-end" in out


def test_elbow_edges_get_rounded_corners(cache):
    out = render("title: T\nnodes:\n  a: { icon: lambda, at: [0, 0] }\n  b: { icon: ddb, at: [1, 1] }\n"
                 "edges:\n  - { from: a, to: b }\n")
    assert " Q" in out  # a quadratic at the corner, not a sharp join


def test_awsres_icons_come_from_the_resource_archive(empty_cache):
    pack = icons.get_pack("awsres")
    blob = make_zip({pack.aliases["ec2"]: (FIX / "service.svg").read_bytes(),
                     "Resource-Icons_07312026/Res_Compute/.DS_Store": b"junk"})
    assert icons.fetch(pack, download=lambda url: blob) == 1
    out = render("title: T\nnodes:\n  a: { icon: awsres:ec2, at: [0, 0] }\n")
    assert '<rect class="tile"' in out and "#ED7100" in out  # resource glyphs keep their colour, on a tile
