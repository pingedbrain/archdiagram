# archdiagram spec reference

A spec is one YAML file that describes one figure. `archdiagram check` validates it, lays it out
and reports collisions; `archdiagram render` turns it into SVG. Unknown keys are errors (a typo
never fails silently).

## Coordinates in one paragraph

Think in grid cells, not pixels. A node at `at: [col, row]` is centred at
`origin + [col * grid.col, row * grid.row]` px. Fractions are fine (`[3.5, 1]`). The only pixel
values in a spec are `via` waypoints, `canvas` and the `grid` itself. With the defaults, column 0
is x=80, column 1 is x=230; row 0 is y=70, row 1 is y=180.

## Top level

| Key | Type | Default | Meaning |
|---|---|---|---|
| `title` | text, **required** | — | Figure name. Prefix of the `aria-label`; its slug is the default id prefix. |
| `claim` | text | `""` | The one sentence the figure proves. `aria-label` = `"<title>: <claim>"`. |
| `caption` | text | `""` | `<figcaption>`. Explanations live here, not in labels. |
| `icons` | mapping | see below | Which icon packs bare names resolve against. |
| `grid` | mapping | see below | Cell size, origin and icon size. |
| `bands` | list | `[]` | Background bands grouping rows. |
| `zones` | list | `[]` | Rectangular containers around a cell range (VPC-style groups). |
| `legend` | list | `[]` | Optional legend box, bottom-left of the figure. |
| `nodes` | mapping, **required** | — | `id: node`. Ids match `[A-Za-z_][A-Za-z0-9_-]*`. |
| `edges` | list | `[]` | Arrows between nodes. |
| `canvas` | `[width, height]` px | auto | Fixed viewBox `0 0 w h`. Auto = bounding box of everything + 16 px. With a fixed canvas, anything outside is an `out_of_canvas` problem. |
| `prefix` | text | slug of `title` | Prefix for every SVG id. Set it when two figures share a title on one page. |

## `icons`

| Key | Default | Meaning |
|---|---|---|
| `packs` | `[aws, generic]` | Order in which a bare icon name is looked up. |
| `monochrome` | `[]` | Packs drawn in `currentColor` instead of their brand colour. Only affects `brand`. |

Icon references in nodes:

- `pack:name` — always unambiguous: `aws:lambda`, `gcp:cloud-run`, `azure:functions`,
  `k8s:pod`, `brand:jira`, `generic:users`.
- `name` — looked up in `icons.packs` order. Found in two packs → `ambiguous_icon`; found in none
  → `unknown_icon` with the closest names. Prefer `pack:name` in specs you will keep.
- A name is an alias from the pack manifest, or (once the pack is fetched) any SVG file stem in
  it, e.g. `aws:Arch_Amazon-Kinesis_48`, `brand:postgresql`. `archdiagram icons list --grep x`.

| Pack | Source | Native box | Drawn as |
|---|---|---|---|
| `aws` | AWS Architecture Icons 07312026 | 64, coloured square | as is |
| `awsres` | AWS Resource Icons 07312026 | 48 glyph, service colour | on a tile |
| `generic` | AWS `Res_General-Icons` light | 48 glyph, ink → `currentColor` | on a tile |
| `gcp` | Google Cloud core product icons | 512, multicolour | on a tile |
| `azure` | Azure Public Service Icons V24 | 18, multicolour | as is |
| `k8s` | kubernetes/community, unlabeled | heptagon, blue | as is |
| `brand` | Simple Icons 16.34.0 (CC0) | 24 glyph, one colour | on a tile, brand hex |

Every icon is scaled into the node's `size` box. Packs with `tile = true` get a rounded tile
(`--surface` fill, `--line` stroke) and the glyph inside at `inset` × size, so a Jira mark next to
a Lambda reads as the same kind of object. Brand colours too dark for a dark theme (luminance
< 0.05: GitHub, Notion, Anthropic...) are drawn in `currentColor` automatically.

## `grid`

| Key | Default | Meaning |
|---|---|---|
| `col` | `150` | px between column centres. |
| `row` | `110` | px between row centres. |
| `origin` | `[80, 70]` | px centre of cell `[0, 0]`. |
| `icon` | `44` | Default icon size in px. |

## `bands[]`

| Key | Type | Default | Meaning |
|---|---|---|---|
| `label` | text, **required** | — | Small caps title at the band's top-left. Write it in capitals. |
| `rows` | `[first, last]`, **required** | — | Rows covered (fractions allowed). |
| `style` | `solid` \| `dashed` | `solid` | `solid` = filled `--sunken`; `dashed` = outline only. |

A band spans the full content width, from 40 px above the first row's icons to 68 px below the
last row's icons (room for label + sub). Leave about 1.5 rows between two bands.

## `zones[]`

A zone is a rectangular container — the AWS way of drawing a VPC, a subnet, a region: a border
around a set of nodes, not an icon. `check` requires every element to sit fully inside or fully
outside a zone (a node or label on the border is an `overlap`), and zones that overlap must
contain one another (nesting a subnet inside a VPC is fine; a partial crossing is not).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `cells` | `[col1, row1, col2, row2]`, **required** | — | Inclusive grid-cell range the zone covers. |
| `label` | text | `""` | Small caps title inside the top-left corner, next to the badge. |
| `style` | `solid` \| `dashed` \| `dotted` | `dashed` | `dashed`/`dotted` draw only the border (the AWS look); `solid` fills `--sunken`. |
| `badge` | icon reference | `""` | Small icon at the top-left corner, AWS group style: `aws:group-vpc`, `aws:public-subnet`, `aws:aws-cloud`. |
| `tint` | `orange` \| `green` \| `blue` \| `purple` \| `gray` \| `red` | `""` | Border colour, the AWS group palette (VPC orange, public subnet green, private blue). |

The left and right borders run at the edges of the first and last column (midway through the
gutter); the top and bottom leave 40 px / 68 px of room around the icons so labels and subs fit.
Give a zone an extra column if a node's `label_side: left|right` text needs the room. Zones may
nest; draw order is biggest first so a solid parent sits behind a solid child.

```yaml
zones:
  - { cells: [0, 0, 2.4, 1], label: "VPC 10.0.0.0/16", style: dashed, badge: aws:group-vpc }
  - { cells: [0, 0, 1, 0], label: "public subnet", style: dotted, badge: aws:public-subnet }
```

## `nodes.<id>`

| Key | Type | Default | Meaning |
|---|---|---|---|
| `icon` | text, **required** | — | Icon reference, see `icons`. |
| `at` | `[col, row]`, **required** | — | Grid cell of the icon centre. |
| `label` | text | `""` | Bold name (14 px). |
| `sub` | text | `""` | Detail line under the label (11.5 px, muted). |
| `accent` | bool | `false` | The node the argument hinges on: blue ring 8 px outside the icon, blue 16 px label. |
| `size` | px | `grid.icon` | Icon size. Accent nodes usually use 52. |
| `label_side` | `below` \| `left` \| `right` | `below` | `below`: centred, baseline 18 px under the icon (+8 with ring), sub 15 px lower. `left`/`right`: same baselines, right-/left-aligned 8 px outside the icon, which frees the space straight below for an edge. |
| `mono` | bool | `false` | Label in the monospace font, for identifiers (`agent_settings`). |

## `edges[]`

| Key | Type | Default | Meaning |
|---|---|---|---|
| `from`, `to` | node id, **required** | — | Unknown ids are `bad_ref` problems. |
| `label` | text | `""` | 11.5 px text on the edge. Keep it ≤ ~28 chars. |
| `route` | `auto` \| `hv` \| `vh` | `auto` | `auto` = straight if the two centres share a row or column, else `hv`. `hv` = horizontal first, then vertical; `vh` = the reverse. |
| `via` | list of `[x, y]` px | `[]` | Explicit waypoints; overrides `route`. |
| `accent` | bool | `false` | Blue, thicker, blue arrowhead and label. |
| `dashed` | bool | `false` | Static dashed line, for async or optional links. |
| `both` | bool | `false` | Arrowhead at both ends (request/response). |
| `flow` | bool \| `dots` \| `ants` | `false` | Animated traffic. `true`/`dots` = packets travel the path (SMIL); `ants` = marching dashes (CSS). Packets hide and dashes stop under `prefers-reduced-motion`. |
| `label_side` | `above` \| `below` \| `left` \| `right` | auto | Picks the segment *and* the side: `above`/`below` use the longest horizontal segment, `left`/`right` the longest vertical one. |

Edge geometry:

- Edges start and end 4 px outside the icon (outside the ring for accent nodes). An edge leaving
  through the bottom of a node whose label is `below` starts under the label block instead.
- With `via`, the first leg leaves the source orthogonally: if the first waypoint's x is within the
  node's half-width, it leaves vertically at that x; if its y is within the half-height, it leaves
  horizontally at that y; otherwise it leaves horizontally from the centre and turns. The last leg
  enters the target the same way. So `via: [[876, 300]]` from a node at x=900 leaves upward at
  x=876. Waypoints inside a node are `bad_via` problems.
- Default label: midpoint of the longest segment, baseline 9 px above a horizontal segment, or
  8 px to the right of a vertical one.
- Edges that share a source (a fork) or a target (a merge) may overlap on purpose; any other
  collinear overlap between edges is a problem.
- Elbow corners render rounded. Where a vertical edge segment crosses another edge's horizontal
  wire, it draws a small jump arc (the circuit-diagram hop); forks/merges never hop.

## `legend[]`

An optional legend box at the bottom-left of the figure. Each item is one row: a swatch plus text.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `text` | text, **required** | — | Row label (11.5 px). |
| `sample` | `edge` \| `accent` \| `dashed` \| `dots` \| `ants` \| `zone` \| `zone-dotted` | — | Line/zone swatch. Give exactly one of `sample` or `icon`. |
| `icon` | icon reference | — | Draw that icon as the swatch. |
| `tint` | same values as `zones[].tint` | `""` | Tint the `zone` swatch to match a tinted zone. |

```yaml
legend:
  - { sample: accent, text: "camino crítico" }
  - { sample: dashed, text: "async / opcional" }
  - { sample: zone-dotted, tint: green, text: "public subnet" }
  - { icon: aws:lambda, text: "serverless" }
```

## What `check` reports

`archdiagram check spec.yaml --json` prints one line per file:

```json
{"file": "spec.yaml", "ok": false, "problems": [
  {"kind": "overlap", "element": "edge lib->spend label", "with": "node spend sub",
   "box": [754, 304, 792, 317], "message": "edge lib->spend label 'suma costo' [754, 304, 860, 317] overlaps node spend sub 'DynamoDB' [748, 301, 792, 345] at [754, 304, 792, 317]",
   "suggestion": "set label_side: left on edge lib->spend"}]}
```

| kind | Meaning |
|---|---|
| `bad_input` | YAML or schema error; the message starts with the path (`nodes.gk.at: required`). Exit 2. |
| `unknown_icon` / `ambiguous_icon` / `unknown_pack` | Icon reference does not resolve; suggestion lists closest `pack:name`. |
| `bad_ref` | Edge endpoint is not a node id. |
| `bad_via` | A waypoint is inside a node. |
| `overlap` | Two elements' boxes intersect: text/text, text/icon, icon/icon, edge/icon, edge/text, edge/edge, band/band; or an element crosses a zone border, or two zones / a zone and a band partially overlap (nesting is fine). |
| `out_of_canvas` | Only with a fixed `canvas`. |

Suggestions are verified: each candidate (another `label_side`, another `route`, moving a node by
half or one cell) is applied to a copy of the spec and re-checked, and only fixes that remove the
overlap without adding another are offered. Text boxes are estimated as
`chars × size × 0.56` wide (mono 0.62, band titles 0.64) and `size × 1.2` high.

## Example

```yaml
title: Agent Platform
claim: el gatekeeper lee settings y reserva presupuesto antes de invocar
caption: En azul, lo único que corre antes de invocar.
icons: { packs: [aws, generic] }
grid: { col: 150, row: 110, origin: [80, 70], icon: 44 }
bands:
  - { label: "EN CADA INVOCACIÓN · DECIDE", rows: [0, 1.3], style: solid }
nodes:
  apigw:    { icon: aws:apigw, at: [0, 0], label: API Gateway, sub: webhooks · pública }
  gk:       { icon: aws:lambda, at: [1.5, 0], label: Gatekeeper, sub: Lambda, accent: true, size: 52, label_side: left }
  settings: { icon: aws:ddb, at: [1.5, 1.3], label: agent_settings, sub: DynamoDB, mono: true }
  runtime:  { icon: aws:agentcore, at: [3, 0], label: AgentCore, sub: runtimes }
edges:
  - { from: apigw, to: gk, label: valida la firma }
  - { from: gk, to: settings, label: "1 · lee", accent: true, label_side: left }
  - { from: gk, to: runtime, label: "2 · invoca", accent: true }
```

Full examples: `examples/mixed.yaml`, `examples/multi-cloud.yaml`.

YAML traps: quote `off`, `on`, `yes`, `no` (they are booleans) and any text with `, : # [ ] { }`
inside a flow mapping (`label: "1 · lee"`, `sub: "stage: opcional"`).
