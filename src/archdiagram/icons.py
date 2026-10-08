"""Icon packs: manifests, the download cache, name resolution and <symbol> building.

A pack is a TOML manifest in `packs/`. `fetch` downloads its official archive (or file list) once
into the cache and keeps only the SVGs it needs. Nothing here touches the network except `fetch`.
"""

from __future__ import annotations

import difflib
import fnmatch
import io
import json
import os
import re
import tarfile
import tomllib
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path, PurePosixPath

PACKS_DIR = Path(__file__).parent / "packs"
USER_AGENT = "archdiagram/0.1 (+icon fetch)"


@dataclass(frozen=True)
class Pack:
    name: str
    title: str
    version: str
    homepage: str
    license: str
    kind: str  # "archive" | "files"
    url: str
    include: tuple[str, ...]
    color: str  # "keep" | "ink" | "brand"
    ink: str = ""
    brand_data: str = ""
    tile: bool = False
    inset: float = 1.0
    aliases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IconRef:
    pack: str
    name: str
    rel: str  # path inside the pack directory


class IconError(Exception):
    def __init__(self, kind: str, message: str, suggestion: str):
        super().__init__(message)
        self.kind, self.message, self.suggestion = kind, message, suggestion


def parse_manifest(data: dict) -> Pack:
    src = data["source"]
    return Pack(
        name=data["name"], title=data["title"], version=str(data["version"]),
        homepage=data.get("homepage", ""), license=data.get("license", ""),
        kind=src["kind"], url=src["url"], include=tuple(data.get("include", ["*.svg"])),
        color=data.get("color", "keep"), ink=data.get("ink", ""), brand_data=data.get("brand_data", ""),
        tile=data.get("tile", False), inset=data.get("inset", 1.0), aliases=dict(data.get("aliases", {})),
    )


@cache
def packs() -> dict[str, Pack]:
    out = {}
    for f in sorted(PACKS_DIR.glob("*.toml")):
        p = parse_manifest(tomllib.loads(f.read_text(encoding="utf-8")))
        out[p.name] = p
    return out


def get_pack(name: str) -> Pack:
    if name not in packs():
        raise IconError("unknown_pack", f"unknown icon pack {name!r}", f"use one of: {', '.join(packs())}")
    return packs()[name]


def cache_root() -> Path:
    return Path(os.environ.get("ARCHDIAGRAM_CACHE") or Path.home() / ".cache" / "archdiagram")


def pack_dir(pack: Pack) -> Path:
    return cache_root() / f"{pack.name}-{pack.version}"


def is_fetched(pack: Pack) -> bool:
    return (pack_dir(pack) / ".complete").exists()


# ---------------------------------------------------------------- fetch


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 - manifest URLs are https constants
        return resp.read()


def _safe_member(name: str) -> str | None:
    """Normalised relative path, or None for anything that could escape the pack dir or is junk."""
    p = PurePosixPath(name.replace("\\", "/"))
    parts = [x for x in p.parts if x not in ("", ".")]
    if not parts or p.is_absolute() or ".." in parts or parts[0] == "__MACOSX":
        return None
    return "/".join(parts)


def _archive_members(blob: bytes):
    """Yield (name, bytes) for every regular file in a zip or tar(.gz) archive."""
    if zipfile.is_zipfile(io.BytesIO(blob)):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for info in z.infolist():
                if not info.is_dir():
                    yield info.filename, z.read(info)
        return
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as t:
        for m in t:
            if m.isfile():
                yield m.name, t.extractfile(m).read()


def install_archive(pack: Pack, blob: bytes) -> int:
    """Extract the pack's SVGs (and brand colour data) from an archive into the cache."""
    dest = pack_dir(pack)
    count = 0
    for raw, data in _archive_members(blob):
        name = _safe_member(raw)
        if name is None:
            continue
        if pack.brand_data and name == pack.brand_data:
            entries = json.loads(data)
            entries = entries.get("icons", entries) if isinstance(entries, dict) else entries
            colors = {e["slug"]: e["hex"] for e in entries if "slug" in e and "hex" in e}
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "colors.json").write_text(json.dumps(colors, sort_keys=True), encoding="utf-8")
            continue
        if not name.endswith(".svg") or not any(fnmatch.fnmatch(name, g) for g in pack.include):
            continue
        out = dest / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        count += 1
    if count:
        (dest / ".complete").write_text(f"{pack.name} {pack.version} {count} svgs\n", encoding="utf-8")
    return count


def fetch(pack: Pack, download=_download) -> int:
    """Download a pack into the cache. Archives are kept under downloads/ so packs sharing one reuse it."""
    if is_fetched(pack):
        return 0
    if pack.kind == "files":
        dest = pack_dir(pack)
        for rel in sorted(set(pack.aliases.values())):
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(download(pack.url + urllib.parse.quote(rel)))
        (dest / ".complete").write_text(f"{pack.name} {pack.version} {len(pack.aliases)} svgs\n", encoding="utf-8")
        return len(set(pack.aliases.values()))
    archive = cache_root() / "downloads" / PurePosixPath(urllib.parse.urlparse(pack.url).path).name
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        part = archive.with_suffix(archive.suffix + ".part")
        part.write_bytes(download(pack.url))
        part.rename(archive)
    return install_archive(pack, archive.read_bytes())


# ---------------------------------------------------------------- resolve


@cache
def _file_index(directory: str) -> dict[str, str]:
    root = Path(directory)
    out: dict[str, str] = {}
    for f in sorted(root.rglob("*.svg")):
        out.setdefault(f.stem, f.relative_to(root).as_posix())
    return out


def names(pack: Pack) -> dict[str, str]:
    """Every name valid in a pack: aliases, plus every SVG file stem once the pack is fetched."""
    out = dict(_file_index(str(pack_dir(pack)))) if is_fetched(pack) else {}
    out.update(pack.aliases)
    return out


def resolve(ref: str, order: tuple[str, ...]) -> IconRef:
    """`pack:name` or a bare `name` looked up in `order`. Raises IconError with a concrete fix."""
    if ":" in ref:
        pack_name, name = ref.split(":", 1)
        pack = get_pack(pack_name)
        table = names(pack)
        if name in table:
            return IconRef(pack.name, name, table[name])
        raise _unknown(ref, [pack])
    candidates = [get_pack(p) for p in order]
    hits = [p for p in candidates if ref in names(p)]
    if len(hits) == 1:
        return IconRef(hits[0].name, ref, names(hits[0])[ref])
    if len(hits) > 1:
        options = " or ".join(f"{p.name}:{ref}" for p in hits)
        raise IconError("ambiguous_icon", f"icon {ref!r} exists in packs {', '.join(p.name for p in hits)}",
                        f"write the pack explicitly: icon: {options}")
    raise _unknown(ref, candidates)


def _unknown(ref: str, candidates: list[Pack]) -> IconError:
    name = ref.split(":", 1)[-1]
    pool = [f"{p.name}:{n}" for p in candidates for n in names(p)]
    close = difflib.get_close_matches(name, [x.split(":", 1)[1] for x in pool], n=4, cutoff=0.5)
    matches = [x for x in pool if x.split(":", 1)[1] in close][:4]
    unfetched = [p.name for p in candidates if not is_fetched(p)]
    hint = f"closest: {', '.join(matches)}" if matches else "run `archdiagram icons list --grep <word>`"
    if unfetched:
        hint += f"; raw file stems need the package: archdiagram icons fetch {' '.join(unfetched)}"
    where = ", ".join(p.name for p in candidates)
    return IconError("unknown_icon", f"icon {ref!r} not found in packs {where}", hint)


# ---------------------------------------------------------------- symbols


_JUNK = [
    re.compile(r"<\?xml.*?\?>", re.S),
    re.compile(r"<!DOCTYPE.*?>", re.S),
    re.compile(r"<!--.*?-->", re.S),
    re.compile(r"<(title|desc|metadata)\b.*?</\1>", re.S),
    re.compile(r"<sodipodi:\w+\b[^>]*/>", re.S),
    re.compile(r"<sodipodi:(\w+)\b.*?</sodipodi:\1>", re.S),
    re.compile(r"\s(?:inkscape|sodipodi):[\w-]+=\"[^\"]*\""),
]


def _inline_css(svg: str) -> str:
    """Turn `.cls { fill: x }` rules into style attributes, drop <style> and every class.

    Embedded <style> is global in an HTML page: two icons' `.st1` rules would recolour each other,
    and an icon's `class="a"` would pick up the diagram's own `.arch .a` arrow rule.
    """
    rules: dict[str, str] = {}

    def grab(m: re.Match) -> str:
        css = re.sub(r"<!\[CDATA\[|\]\]>|/\*.*?\*/", "", m.group(1), flags=re.S)
        for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
            decl = "".join(f"{d.strip()};" for d in body.split(";") if d.strip())
            for s in sel.split(","):
                s = s.strip()
                if re.fullmatch(r"\.[\w-]+", s):
                    rules[s[1:]] = rules.get(s[1:], "") + decl
        return ""

    svg = re.sub(r"<style\b[^>]*>(.*?)</style>", grab, svg, flags=re.S)

    def tag(m: re.Match) -> str:
        t = m.group(0)
        cm = re.search(r'\sclass="([^"]*)"', t)
        if not cm:
            return t
        decl = "".join(rules.get(c, "") for c in cm.group(1).split())
        t = t.replace(cm.group(0), "", 1)
        if not decl:
            return t
        sm = re.search(r'\sstyle="([^"]*)"', t)
        if sm:
            return t.replace(sm.group(0), f' style="{decl}{sm.group(1)}"', 1)
        return re.sub(r"^(<[\w:-]+)", lambda x: f'{x.group(1)} style="{decl}"', t)

    return re.sub(r"<[A-Za-z][^>]*>", tag, svg)


def _prefix_ids(inner: str, prefix: str) -> str:
    ids = set(re.findall(r'\sid="([^"]+)"', inner))
    new = {old: prefix + re.sub(r"[^A-Za-z0-9_-]", "-", old) for old in ids}
    inner = re.sub(r'(\sid=")([^"]+)(")', lambda m: m.group(1) + new.get(m.group(2), m.group(2)) + m.group(3), inner)
    inner = re.sub(r"url\(\s*['\"]?#([^)'\"]+)['\"]?\s*\)", lambda m: f"url(#{new.get(m.group(1), m.group(1))})", inner)
    return re.sub(r'((?:xlink:)?href=")#([^"]+)(")', lambda m: f"{m.group(1)}#{new.get(m.group(2), m.group(2))}{m.group(3)}", inner)


def _dark(hex_color: str) -> bool:
    """True when a brand colour would vanish on a dark surface (GitHub, Notion, Anthropic...)."""
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2] < 0.05


def build_symbol(pack: Pack, ref: IconRef, symbol_id: str, monochrome: bool = False) -> str:
    """One official SVG -> `<symbol>` with prefixed internal ids and the pack's colour policy."""
    src = (pack_dir(pack) / ref.rel).read_text(encoding="utf-8")
    for rx in _JUNK:
        src = rx.sub("", src)
    root = re.search(r"<svg\b[^>]*>", src)
    if root is None:
        raise IconError("bad_icon", f"{pack.name}:{ref.name} is not an SVG ({ref.rel})", "re-fetch the pack")
    vb = re.search(r'viewBox="([^"]+)"', root.group(0))
    if vb:
        viewbox = " ".join(vb.group(1).replace(",", " ").split())
    else:
        w = re.search(r'\swidth="([\d.]+)', root.group(0))
        h = re.search(r'\sheight="([\d.]+)', root.group(0))
        viewbox = f"0 0 {w.group(1) if w else 24} {h.group(1) if h else 24}"
    inner = src[root.end():src.rfind("</svg>")]
    inner = _prefix_ids(_inline_css(inner), f"{symbol_id}-")
    if pack.color == "ink" and pack.ink:
        inner = re.sub(pack.ink, "currentColor", inner, flags=re.I)
    elif pack.color == "brand":
        # `monochrome` only means something for brand glyphs; coloured tiles (aws, azure) stay official.
        colors_file = pack_dir(pack) / "colors.json"
        colors = json.loads(colors_file.read_text(encoding="utf-8")) if colors_file.exists() else {}
        hex_color = colors.get(Path(ref.rel).stem)
        fill = "currentColor" if monochrome or not hex_color or _dark(hex_color) else f"#{hex_color}"
        inner = f'<g fill="{fill}">{inner}</g>'
    inner = re.sub(r">\s+<", "><", inner).strip()
    return f'<symbol id="{symbol_id}" viewBox="{viewbox}">{inner}</symbol>'
