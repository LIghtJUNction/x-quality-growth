---
name: RISE
description: SVG identity and recorded-metric graphics for the RISE README.
colors:
  primary: "#d8462f"
  metric-accent: "#b73825"
  pending: "#8b5520"
  neutral-bg: "#f5f1e9"
  ink: "#191b1b"
  body: "#454a48"
  muted: "#636660"
  rule: "#d8d1c6"
  circuit: "#dbd4c9"
  metric-surface: "#eae4da"
  badge-bg: "#1b2733"
  badge-text: "#ecf5f8"
rounded:
  canvas: "24px"
  metric-card: "12px"
  badge: "8px"
---

## Overview

This records the built SVG header, metric graphics and badges used in the README. It is not a website design system. The header pairs a large authored RISE wordmark with a compact feedback circuit: publishing, open-source collaboration, observed feedback and iteration. The circuit describes a process; it does not predict growth.

The revised static header has a reviewer disposition of **ship** at desktop and 640px render widths. Animation playback was also verified in the public GitHub README: sequential browser captures showed the accent segment at different positions on the closed circuit.

## Colors

Warm paper carries the header and metric canvases. Ink establishes the wordmark, titles, diagram nodes and main values. Vermilion marks the moving feedback segment and small identity accents; metric red distinguishes recorded counts and bars. Brown carries pending classification and evidence caveats. Muted text and fine warm rules support secondary information.

The existing compact badges use dark blue backgrounds and pale text. Preserve that separate badge treatment rather than assuming they already use the paper canvas.

## Typography

The RISE wordmark is authored vector geometry, independent of installed fonts. Preserve its paths and proportions. The header's Chinese title uses Noto Sans CJK SC, Microsoft YaHei, then sans-serif (60px, weight 800); diagram labels use the same stack (19px, weight 700). Latin text uses Noto Sans, Helvetica Neue, then sans-serif. Generated metrics and badges use Arial, then sans-serif.

Treat vector lettering and live text differently: the wordmark is stable; CJK rendering still depends on the viewer's fonts.

## Layout

The header has a fixed viewBox (1200 × 580). Identity and title occupy the left side; a thin vertical rule separates the right-hand four-node circuit. A bottom rule anchors provenance and the forecast caveat. The complete composition scales with the README image width; there is no authored mobile reflow.

Metrics use a shared canvas width (1100 units), a 38-unit left inset and three summary cards. The follower comparison uses a zero-based absolute bar scale. Feedback rows keep five counter columns and observation timestamps together. Check small-width legibility whenever labels or rows change; the static header review does not establish metric readability at every width.

## Elevation & Depth

Flat fills, fine rules and strokes establish hierarchy. These assets use no shadows or dimensional effects.

## Shapes

Soft canvas corners and metric cards contrast with the firm wordmark. The feedback circuit is a rounded closed path with four circular nodes and authored line icons. Keep the diagram sparse enough that its labels remain distinguishable when scaled.

## Components

- **Header:** `assets/rise-hero.svg` contains the wordmark, CJK title, four-node diagram, accessible title and description. The vermilion segment uses CSS `stroke-dashoffset` on a loop length of 1114.655 units, with a linear 14-second repeat. `prefers-reduced-motion: reduce` disables animation while retaining the visible segment.
- **Metrics and feedback:** `scripts/render_public.py` generates `assets/metrics.svg`, `assets/feedback.svg` and controlled README metric blocks from `public/metrics.json`. Preserve observation timestamps, sample counts and explanatory caveats. Unclassified quality yields **PENDING**; absent counters yield **N/A**. Unknown is never converted into zero. A blue-badge list change is not proof of a newly gained follower, and observed engagement is not proof of causal lift.
- **Badges:** the existing `assets/badge*.svg` files are 32 units high, with compact Arial labels and SVG titles for algorithm provenance, real-data semantics and license.

## Do's and Don'ts

**The evidence rule.** Display only recorded observations, keep their uncertainty visible, and regenerate metrics through the script when data changes. Do not invent gains, hide pending classifications or remove caveats to simplify a graphic.

**The identity rule.** Preserve the authored wordmark, warm paper, ink hierarchy and vermilion circuit. Keep new work within the SVG/README scope; do not infer website navigation or product flows from these assets.

**The verification rule.** Distinguish reviewed static renders from runtime motion. Verify animation in the public rendering environment before claiming that the published header animates.
