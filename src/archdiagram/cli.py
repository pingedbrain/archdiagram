"""archdiagram CLI. Non-interactive and deterministic. Exit codes: 0 ok, 1 problems, 2 bad input."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path

from . import collide, icons, render
from .layout import layout
from .spec import SpecError, load

OK, PROBLEMS, BAD_INPUT = 0, 1, 2


def _check_one(path: str, as_json: bool) -> int:
    try:
        spec = load(path)
    except SpecError as exc:
        if as_json:
            print(json.dumps({"file": path, "ok": False, "problems": [
                {"kind": "bad_input", "element": "spec", "with": "", "box": None, "message": m,
                 "suggestion": "fix the field named before the colon; see docs/spec.md"} for m in exc.errors]}, ensure_ascii=False))
        else:
            print(f"{path}: bad input", file=sys.stderr)
            for m in exc.errors:
                print(f"  {m}", file=sys.stderr)
        return BAD_INPUT
    problems = collide.check(spec)
    if as_json:
        print(json.dumps({"file": path, "ok": not problems, "problems": [p.to_dict() for p in problems]}, ensure_ascii=False))
    elif not problems:
        print(f"{path}: ok")
    else:
        print(f"{path}: {len(problems)} problem{'s' if len(problems) > 1 else ''}")
        for p in problems:
            print(f"  [{p.kind}] {p.message}\n    fix: {p.suggestion}")
    return PROBLEMS if problems else OK


def cmd_check(args) -> int:
    return max(_check_one(f, args.json) for f in args.spec)


def cmd_render(args) -> int:
    if not args.output and not args.fragment:
        print("render: give -o out.svg|out.html, or --fragment to print the <figure> to stdout", file=sys.stderr)
        return BAD_INPUT
    if args.output and Path(args.output).suffix not in (".svg", ".html"):
        print(f"render: output must end in .svg or .html, got {args.output}", file=sys.stderr)
        return BAD_INPUT
    try:
        spec = load(args.spec)
    except SpecError as exc:
        print("\n".join(exc.errors), file=sys.stderr)
        return BAD_INPUT
    stop = collide.blocking(collide.check(spec), args.force)
    if stop:
        print(f"{args.spec}: refusing to render, {len(stop)} problem(s); run `archdiagram check` (or --force for layout-only problems)", file=sys.stderr)
        for p in stop:
            print(f"  [{p.kind}] {p.message}\n    fix: {p.suggestion}", file=sys.stderr)
        return PROBLEMS
    lay = layout(spec)
    try:
        if args.fragment:
            sys.stdout.write(render.fragment(spec, lay))
        if args.output:
            out = Path(args.output)
            text = render.standalone_svg(spec, lay) if out.suffix == ".svg" else render.page(spec, lay)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(f"wrote {out}", file=sys.stderr)
    except icons.IconError as exc:
        print(f"[{exc.kind}] {exc.message}\n    fix: {exc.suggestion}", file=sys.stderr)
        return PROBLEMS
    return OK


def cmd_css(_args) -> int:
    sys.stdout.write(render.css())
    return OK


def cmd_icons_fetch(args) -> int:
    names = args.pack or sorted(icons.packs())
    code = OK
    for name in names:
        try:
            pack = icons.get_pack(name)
        except icons.IconError as exc:
            print(f"{exc.message}; {exc.suggestion}", file=sys.stderr)
            code = BAD_INPUT
            continue
        if icons.is_fetched(pack):
            print(f"{name}: already cached at {icons.pack_dir(pack)}")
            continue
        try:
            n = icons.fetch(pack)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"{name}: fetch failed from {pack.url}: {exc}\n  offline? see README 'Offline cache'", file=sys.stderr)
            code = PROBLEMS
            continue
        print(f"{name}: {n} svgs -> {icons.pack_dir(pack)}")
    return code


def cmd_icons_list(args) -> int:
    names = [args.pack] if args.pack else sorted(icons.packs())
    grep = (args.grep or "").lower()
    for name in names:
        try:
            pack = icons.get_pack(name)
        except icons.IconError as exc:
            print(f"{exc.message}; {exc.suggestion}", file=sys.stderr)
            return BAD_INPUT
        if not icons.is_fetched(pack):
            print(f"# {name}: not fetched, showing aliases only (archdiagram icons fetch {name})", file=sys.stderr)
        for n, rel in sorted(icons.names(pack).items()):
            if grep in n.lower() or grep in rel.lower():
                kind = "alias" if n in pack.aliases else "file"
                print(f"{name}:{n}\t{kind}\t{rel}")
    return OK


def cmd_icons_packs(_args) -> int:
    for p in icons.packs().values():
        state = "fetched" if icons.is_fetched(p) else "not fetched"
        print(f"{p.name}\t{p.version}\t{state}\t{p.title}\n\tlicense: {p.license}\n\tsource: {p.url}")
    return OK


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="archdiagram", description="YAML spec -> themeable architecture diagram (inline SVG).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="validate, lay out and collision-check specs")
    c.add_argument("spec", nargs="+")
    c.add_argument("--json", action="store_true", help="one JSON object per spec, one per line")
    c.set_defaults(fn=cmd_check)

    r = sub.add_parser("render", help="render a spec to .svg / .html, or a <figure> fragment on stdout")
    r.add_argument("spec")
    r.add_argument("-o", "--output")
    r.add_argument("--fragment", action="store_true", help="print <figure class=\"arch\">...</figure> to stdout")
    r.add_argument("--force", action="store_true", help="render despite overlaps / out_of_canvas")
    r.set_defaults(fn=cmd_render)

    s = sub.add_parser("css", help="print the .arch stylesheet to paste once into a page")
    s.set_defaults(fn=cmd_css)

    i = sub.add_parser("icons", help="icon packs: fetch, list, packs")
    isub = i.add_subparsers(dest="icmd", required=True)
    f = isub.add_parser("fetch", help="download packs into the cache (default: all)")
    f.add_argument("pack", nargs="*")
    f.set_defaults(fn=cmd_icons_fetch)
    li = isub.add_parser("list", help="print pack:name for every alias and (once fetched) file stem")
    li.add_argument("--pack")
    li.add_argument("--grep")
    li.set_defaults(fn=cmd_icons_list)
    pk = isub.add_parser("packs", help="show packs, versions, cache state and licences")
    pk.set_defaults(fn=cmd_icons_packs)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
