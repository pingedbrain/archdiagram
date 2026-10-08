"""Manifests are data an agent edits: keep them loadable, and their aliases real once a pack is cached."""

import pytest

from archdiagram import icons


def test_every_manifest_loads_with_a_source_and_aliases():
    packs = icons.packs()
    assert {"aws", "gcp", "azure", "k8s", "brand", "generic"} <= set(packs)
    for p in packs.values():
        assert p.kind in ("archive", "files") and p.url.startswith("https://") and p.aliases
        assert p.color in ("keep", "ink", "brand")


@pytest.mark.parametrize("name", sorted(icons.packs()))
def test_aliases_exist_in_the_real_cached_package(name):
    """Runs only where the real pack is cached (`archdiagram icons fetch`); never downloads."""
    pack = icons.get_pack(name)
    if not icons.is_fetched(pack):
        pytest.skip(f"{name} not cached")
    missing = [a for a, rel in pack.aliases.items() if not (icons.pack_dir(pack) / rel).exists()]
    assert missing == []


def test_files_kind_fetches_each_alias_path(empty_cache):
    pack = icons.get_pack("k8s")
    asked = []
    blob = b'<svg viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg"><path id="p" d="M0 0h18v18H0z"/></svg>'
    count = icons.fetch(pack, download=lambda url: asked.append(url) or blob)
    assert count == len(set(pack.aliases.values())) and icons.is_fetched(pack)
    assert all(u.startswith(pack.url) for u in asked)
    assert icons.resolve("k8s:pod", ()).rel == "resources/unlabeled/pod.svg"
