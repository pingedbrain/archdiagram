# archdiagram

Small YAML spec in, hand-quality architecture diagram out: inline SVG with official provider
icons, themed by CSS custom properties so the same figure reads in light and dark pages. Built
to be driven by coding agents: `check` reports every overlap with a verified fix.

```bash
uv sync
uv run archdiagram icons fetch                 # official icon packages -> ~/.cache/archdiagram
uv run archdiagram check examples/*.yaml       # validate + layout + collisions
uv run archdiagram render examples/mixed.yaml -o out/mixed.html
uv run archdiagram render examples/mixed.yaml --fragment   # <figure> for an existing page
uv run archdiagram css                         # the stylesheet, paste once per page
```

- Spec reference: [docs/spec.md](docs/spec.md)
- Agent instructions: [AGENTS.md](AGENTS.md); portable skill: [skills/archdiagram/SKILL.md](skills/archdiagram/SKILL.md)
- Tests: `uv run pytest` (no network; fake icon packages)

## Icon packs

| Pack | Source | Status |
|---|---|---|
| `aws` | AWS Architecture Icons 07312026 | fetched and rendered |
| `generic` | AWS `Res_General-Icons` (light), recoloured to `currentColor` | fetched and rendered |
| `brand` | Simple Icons 16.34.0 (npm tarball, CC0) | fetched and rendered |
| `k8s` | kubernetes/community icons (CC BY 4.0), pinned commit, file by file | fetched and rendered |
| `gcp` | Google Cloud core product icons | fetched and rendered (`examples/multi-cloud.yaml`) |
| `azure` | Azure Public Service Icons V24 | fetched and rendered (`examples/multi-cloud.yaml`) |

Icons are never committed: each provider allows use in diagrams but not redistribution of the
package. Brand marks remain trademarks of their owners; follow their guidelines and do not imply
endorsement. Simple Icons does not ship Slack or OpenAI marks (removed at the owners' request).

## Offline cache

`ARCHDIAGRAM_CACHE` (default `~/.cache/archdiagram`) holds one directory per pack,
`<pack>-<version>/`, containing the archive's paths plus a `.complete` marker. Without network,
populate it from an already-extracted package, e.g. for AWS:

```bash
C=${ARCHDIAGRAM_CACHE:-~/.cache/archdiagram}/aws-07312026
mkdir -p "$C" && cp -r /path/to/extracted/Architecture-Service-Icons_07312026 "$C"/ && touch "$C/.complete"
```

(`generic-07312026` takes `Resource-Icons_07312026/` the same way.) Or drop the downloaded
archive into `$ARCHDIAGRAM_CACHE/downloads/` under its original file name and run
`archdiagram icons fetch`: it extracts from there without downloading.

## License

Code: MIT, see [LICENSE](LICENSE). Icons are not part of this repository; each pack keeps its
provider's terms (see `archdiagram icons packs`).
