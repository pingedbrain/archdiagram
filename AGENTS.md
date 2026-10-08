# archdiagram — instructions for coding agents

YAML spec -> hand-quality architecture diagram as inline SVG, with official provider icons
(AWS, Google Cloud, Azure, Kubernetes, Simple Icons brands, generic glyphs), themed light/dark by
CSS custom properties. Python >= 3.11, managed with uv, one runtime dependency: `pyyaml`.

## The loop (always)

1. Read `docs/spec.md` once. It is the full reference; this file does not repeat it.
2. Write or edit the YAML spec.
3. Run `uv run archdiagram check spec.yaml --json`.
4. For each problem apply its `suggestion` (they are verified fixes, not guesses). Edit the YAML,
   never the output.
5. Repeat 3-4 until `"ok": true` (exit 0).
6. Render: `uv run archdiagram render spec.yaml -o out.html` (preview page), `-o out.svg`
   (standalone), or `--fragment` (just the `<figure>` to paste into a page).

Exit codes: 0 ok, 1 problems, 2 bad input (YAML/schema; the message names the field path).
`render` refuses while `check` has problems; `--force` overrides overlaps only, never broken refs.

## Conventions for a good figure

- One claim per figure. Write it in `claim`; if you need two sentences, draw two figures.
- Think in grid cells. Place nodes on integer cells; use `.5` steps only to align with something.
  Put pixels only in `via`.
- Main flow left to right on one row; secondary or after-the-fact flows on rows below, grouped
  with a `band`.
- Label every edge with a verb (`lee`, `invoca`, `writes`). Labels and subs ≤ ~28 chars.
- Accent (`accent: true`) only the path the argument hinges on: one node, its edges. Everything
  accented means nothing is.
- Explanations go in `caption`, not in labels.
- Prefer `pack:name` icon references (`aws:lambda`, `brand:jira`); bare names are resolved
  against `icons.packs` and can become ambiguous when you add a pack.
- If an edge must pass under a node's label, set that node's `label_side: left|right`.
- Credit icon sources in the caption when the pack's licence asks for it (k8s: CC BY 4.0).

## Icons

- `uv run archdiagram icons packs` — packs, versions, cache state, licences.
- `uv run archdiagram icons fetch [pack ...]` — download into `~/.cache/archdiagram/`
  (`ARCHDIAGRAM_CACHE` overrides). `check` works without the cache for aliases; `render` needs it.
- `uv run archdiagram icons list [--pack aws] [--grep kinesis]` — every valid `pack:name`.

### Add an alias

Add one line under `[aliases]` in `src/archdiagram/packs/<pack>.toml`, value = path inside the
archive. Find the path with `uv run archdiagram icons list --pack <pack> --grep <word>` (needs the
pack fetched). Then run `uv run pytest tests/test_packs.py` — it fails if an alias points at a
file missing from the cached package.

### Add a pack

1. Create `src/archdiagram/packs/<name>.toml` with: `name`, `title`, `version`, `homepage`,
   `license`, `source = { kind = "archive"|"files", url = "..." }`, `include` (globs of archive
   members to keep), `color` (`keep` | `ink` + `ink = "<regex>"` | `brand` + `brand_data`),
   `tile`, `inset`, and `[aliases]`. Copy the closest existing manifest.
   `kind = "files"` fetches each alias path relative to `url` (for repos too big to download whole).
2. Verify the source and every alias path yourself (`icons fetch <name>`, `icons list`).
3. Add a test that builds a fake archive in memory (see `tests/conftest.py`: `make_zip`,
   `make_tgz`, `icons.fetch(pack, download=lambda url: blob)`) and renders one node.
4. Add the pack to the table in `docs/spec.md` and to `skills/archdiagram/SKILL.md`.

## Code map

- `src/archdiagram/spec.py` — YAML -> frozen dataclasses; structural validation.
- `src/archdiagram/icons.py` — manifests, fetch, resolve, `<symbol>` building (id prefixing,
  CSS inlining, recolouring).
- `src/archdiagram/layout.py` — grid -> px, routing, text placement. Pure.
- `src/archdiagram/collide.py` — boxes, overlaps, verified suggestions, `check()`.
- `src/archdiagram/render.py` — SVG/HTML/fragment and the stylesheet (`archdiagram css`).
- `src/archdiagram/cli.py` — argparse front end.

## Tests

`uv run pytest`. Behaviour-focused, hand-written fakes, no mocks, no network: icon packages are
fake archives built in `tests/conftest.py` from `tests/fixtures/*.svg`. The only test reading the
real cache (`test_packs.py`) skips when a pack is not fetched.

## Do not

- Hand-edit generated SVG/HTML. Change the spec or the code.
- Add dependencies. Stdlib + pyyaml (zipfile, tarfile, urllib, tomllib, difflib cover it).
- Commit icons or downloaded archives. Provider terms allow use in diagrams, not redistribution
  of the packages; `.gitignore` covers the usual paths.
- Hit the network in tests.
- Publish brand logos in ways that imply endorsement; follow each brand's guidelines.
