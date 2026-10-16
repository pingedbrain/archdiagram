---
name: archdiagram
description: Draw architecture diagrams as themeable inline SVG with official provider icons (AWS, Google Cloud, Azure, Kubernetes, brand logos like Jira/GitHub/Sentry, generic glyphs) from a small YAML spec, with a collision checker that tells you how to fix the layout. Use when asked for an architecture diagram, AWS diagram, cloud diagram, system figure, flow with icons, "diagrama", "diagrama de arquitectura", or icons for an HTML page or artifact.
---

# archdiagram

Install once (any repo can then use it):

```bash
uv tool install git+https://github.com/pingedbrain/archdiagram
AD=archdiagram
$AD --help
```

Read `docs/spec.md` (https://github.com/pingedbrain/archdiagram/blob/main/docs/spec.md) before writing the first spec.
Examples: `examples/*.yaml` in the same repo.

## One-time setup

```bash
$AD icons packs            # what exists, licences, cache state
$AD icons fetch aws generic   # or: $AD icons fetch  (all packs, ~22 MB download)
```

The cache is `~/.cache/archdiagram/` (`ARCHDIAGRAM_CACHE` overrides). Never copy icons into the
repo you are working in.

Packs: `aws` (service icons + `group-*`/`public-subnet`/`aws-cloud` group badges for
`zones[].badge`), `awsres` (per-resource glyphs: `awsres:ec2`, `awsres:nat`, `awsres:alb`...),
`generic`, `gcp`, `azure`, `k8s`, `brand`. `zones:` draws VPC-style dashed/dotted containers
around a `cells: [c1, r1, c2, r2]` range — see `docs/spec.md`.

## The loop

1. Write the spec next to the document that will use it (e.g. `docs/figures/platform.yaml`).
   One claim per figure; grid cells, not pixels; label every edge; accent only the decisive path.
2. `$AD check docs/figures/platform.yaml --json`
3. Apply each problem's `suggestion` to the YAML (they are verified). Unknown icon? The
   suggestion lists the closest `pack:name`; or `$AD icons list --grep <word>`.
4. Repeat until `"ok": true` (exit 0). Exit 2 = YAML/schema error, message names the field.
5. Render.

## Putting it into an HTML page or artifact

The figure uses CSS custom properties (`--surface --sunken --fg --fg-2 --fg-3 --line --primary
--primary-soft --font-body --font-mono`), with light fallbacks, so it follows the page theme.

```bash
$AD css > /tmp/arch.css                                  # once per page, into its <style>
$AD render docs/figures/platform.yaml --fragment > /tmp/fig.html   # the <figure class="arch">
```

- Paste the CSS once in the page's `<style>`; paste each fragment where the figure goes.
- Several figures on one page are fine: every id is prefixed with the title slug (`prefix:`
  in the spec overrides it). Give each figure a distinct title or prefix.
- For dark mode, define the tokens under `@media (prefers-color-scheme: dark)` in the page;
  `$AD render x.yaml -o preview.html` shows a full page with both token sets to copy from.
- Standalone file instead: `$AD render x.yaml -o figure.svg` (embeds its own styles).

## Don'ts

- Do not hand-edit the generated SVG; change the YAML and re-render.
- Do not `--force` past overlaps in anything you ship.
- Brand logos (`brand:*`, Simple Icons) are trademarks: use them to name the system, not to
  imply endorsement. Kubernetes icons need credit (CC BY 4.0) in the caption.
