---
name: CODEX-RESET-LIKELIHOOD
description: A black-and-white measurement instrument where fact and inference are drawn in different materials, never different colours.
colors:
  ink: "#ffffff"
  ground: "#000000"
  hair: "rgba(255,255,255,.22)"
  hair-soft: "rgba(255,255,255,.10)"
  hair-row: "rgba(255,255,255,.06)"
  wash-hover: "rgba(255,255,255,.05)"
typography:
  display:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "clamp(20px, 3.4vw, 34px)"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-.01em"
    textTransform: "uppercase"
  headline:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-.01em"
    textTransform: "uppercase"
  title:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "13px"
    fontWeight: 800
    lineHeight: 1.5
    letterSpacing: "-.01em"
    textTransform: "uppercase"
  subtitle:
    fontFamily: "Martian Mono, ui-monospace, monospace"
    fontSize: "11px"
    fontWeight: 800
    lineHeight: 1.5
    letterSpacing: "-.01em"
    textTransform: "uppercase"
  body:
    fontFamily: "Azeret Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 300
    lineHeight: 1.5
    letterSpacing: ".02em"
  data:
    fontFamily: "Azeret Mono, ui-monospace, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: ".02em"
    fontFeature: "tnum 1"
  label:
    fontFamily: "Azeret Mono, ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: ".18em"
    textTransform: "uppercase"
  micro:
    fontFamily: "Azeret Mono, ui-monospace, monospace"
    fontSize: "9px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: ".14em"
    textTransform: "uppercase"
rounded:
  none: "0px"
spacing:
  unit: "4px"
  tight: "8px"
  snug: "12px"
  base: "16px"
  loose: "24px"
  section: "34px"
  tail: "80px"
components:
  panel-hairline:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "{spacing.snug}"
  panel-inverted:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.none}"
    padding: "{spacing.base}"
  chip-hairline:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "1px 6px"
  chip-solid:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "1px 6px"
  tag-synthetic:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "1px 5px"
  banner-synthetic:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "7px 16px"
  nav-link:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "2px 0"
  matrix-cell:
    backgroundColor: "transparent"
    rounded: "{rounded.none}"
    width: "11px"
    height: "11px"
  matrix-cell-hit:
    backgroundColor: "{colors.ink}"
    rounded: "{rounded.none}"
    width: "11px"
    height: "11px"
---

# Design System: CODEX-RESET-LIKELIHOOD

## Overview

**Creative North Star: "The Instrument Face"**

This is the front panel of a measuring device, not a status page. Everything on screen is either something the instrument measured or something it computed from what it measured, and the surface is built so those two can never be confused — not by a reader who is colour-blind, not by a reader who is skimming, not by a reader who never reads the legend. The refusal that shapes the whole world is the status page's single green tick standing in for a claim nobody can audit. This page has no ticks and no green.

The world is pure black ground with pure white marks, at data-sheet density: 10–13px monospace, hairline 1px rules, no radius anywhere, no shadow anywhere, no fill that is not either fully white or fully absent. What reads as grey is white held at low opacity or white hairlines spaced apart — the greys are a *density* effect, never a pigment. Three materials carry all meaning: **solid barcode bars** for measured fact, **hairline curves** for computed inference, and **0/1 cell matrices** for per-day state. A fourth material was named in the direction contract — a sine/wave lattice — and it is **not rendered anywhere in the ship**; it is recorded here as an unbuilt part of the world, not as a token.

Density is deliberate and uniform: no hero whitespace, no breathing room bought at the cost of a row of data. The page reads top to bottom as five numbered instrument sections (01 Field, 02 Event log, 03 Day matrix, 04 Scorecards, 05 Method), each opening with an index numeral, an uppercase title and a right-flushed lowercase note. Emphasis is bought exclusively by inversion — a block flips to white ground with black marks — which is why there is nothing left to spend on colour.

**Key Characteristics:**
- Two pigments only: pure white (`#ffffff`) and pure black (`#000000`). No grey token, no hue.
- Three rendering materials: solid bars (fact), hairline strokes (inference), 0/1 cells (state).
- Zero radius, zero shadow; every container is a 1px hairline rectangle.
- Two monospaced faces only — Martian Mono at display weight, Azeret Mono at data density — with tabular figures throughout.
- Fact/inference distinction survives greyscale, colour-blindness, and screenshots.
- Absent data is written out as `NOT YET SCORED` / `INSUFFICIENT DATA`; fabricated figures wear a `SYNTHETIC` tag.

## Colors

A two-pigment palette: white marks on black ground, where every intermediate tone is opacity or hairline density rather than a colour.

### Primary
- **Signal White** (`#ffffff`): every mark the instrument makes — type, barcode bars, hazard curve stroke, lit matrix cells, and the ground of any inverted block. It is the ink and, when inverted, the surface.

### Neutral
- **Absolute Ground** (`#000000`): the page field and, inside inverted blocks, the ink. Sticky header and banner repaint it opaquely so scrolled content never ghosts through.
- **Hairline** (`rgba(255,255,255,.22)`): every structural border — panel edges, section header rules, chip outlines, axis baselines, interval end-caps. This is the system's only "line" value.
- **Hairline Soft** (`rgba(255,255,255,.10)`): subordinate division — between-section rules, table row rules inside cards, matrix cell outlines, interval mid-axis. Used where a full hairline would out-shout the data.
- **Row Rule** (`rgba(255,255,255,.06)`): the faintest division, used only between dense poll-stream rows where a `.10` rule would read as a grid.
- **Hover Wash** (`rgba(255,255,255,.05)`): the only hover fill in the system, on event-log rows.

Text tone is set by opacity on Signal White, not by a lighter ink: primary `1`, de-emphasised body `.72–.75`, secondary label `.55–.6`, axis and tally micro-copy `.35–.5`, unlit matrix cells `.16`. The background barcode canvas sits at `.5`.

### Named Rules

**The Two-Pigment Rule.** There are exactly two colour values in this system: `#ffffff` and `#000000`. Any tone between them is white at reduced opacity or white hairlines at reduced density. Never introduce a grey token, and never introduce a hue — not for success, not for warning, not for a brand accent.

**The Inversion-Is-Emphasis Rule.** The only way to raise a block above its neighbours is to swap ground and ink: white background, black marks. Measured fact is what earns it (the verdict block, the event row's verdict cell, the synthetic banner, solid chips, tags). Because inversion is the entire emphasis budget, an inverted block on a screen that already has one must justify itself.

**The Colourless Distinction Rule.** No distinction may rest on colour alone — including the black/white pair. Fact and inference are separated four ways simultaneously: inversion, material (SOLID vs HAIRLINE), a literal chip reading `SOLID`/`HAIRLINE`, and the words `FACT`/`INFERENCE` in the track label. Removing any one of these must still leave the reader able to tell them apart. This is a product accessibility constraint, not a stylistic preference.

## Typography

**Display Font:** Martian Mono (fallback `ui-monospace, monospace`), weights 700 and 800
**Data Font:** Azeret Mono (fallback `ui-monospace, monospace`), weights 300, 400 and 600

**Character:** Two monospaced faces doing two different jobs. Martian Mono is wide, mechanical and heavy — it is only ever used uppercase, at heading and headline-number scale, with slightly negative tracking (`-.01em`) so the big words hold together as a block. Azeret Mono is narrow and light and carries everything readable: body copy at 300, data at 400, labels at 600 with wide tracking. Nothing on this page is set in a proportional face; the grid of the monospace *is* the instrument's ruling.

### Hierarchy
- **Display** (Martian Mono 800, `clamp(20px, 3.4vw, 34px)`, line-height 1.05, uppercase): the verdict statement only — the one measured answer the page exists to give.
- **Headline** (Martian Mono 800, 26px, line-height 1): the single published number in a readout (`p24` percentage) and the `INSUFFICIENT DATA` stand-in that replaces it when data is absent. Both occupy the same slot at the same size deliberately.
- **Title** (Martian Mono 800, 13px, uppercase): section headings and the wordmark (wordmark tracks `+.04em` rather than `-.01em` because it must read as a name, not a phrase).
- **Subtitle** (Martian Mono 800, 11px, uppercase): card, readout and method sub-headings.
- **Section index** (Martian Mono 700, 11px, opacity `.45`): the `01`–`05` numerals. The only use of weight 700.
- **Body** (Azeret Mono 300, 12px base / 11px in panels, line-height 1.5–1.7, tracking `.02em`): explanatory prose. Prose is always a subordinate opacity (`.72–.75`) under the figures it explains.
- **Data** (Azeret Mono 400–600, 10.5–11px, tabular figures): tables, readout values, event metadata. Event rows step to 600 to lift them out of the surrounding poll rows.
- **Label** (Azeret Mono 600, 10px, tracking `.18em`, uppercase): panel and track labels, definition terms, legend items.
- **Micro** (Azeret Mono 600, 9px, tracking `.10–.14em`, uppercase): table headers, axis ticks, tags, nav links, weekday tallies.

### Named Rules

**The Tabular Figure Rule.** Every number on this page is set with `font-variant-numeric: tabular-nums` and `font-feature-settings: "tnum" 1`, applied via one class. Columns of figures must align on the digit; a ticking clock must not reflow its neighbours.

**The Two-Face Rule.** Martian Mono is for uppercase display and headline numbers; Azeret Mono is for everything a reader actually reads. A body paragraph never uses the display face, and a display heading never uses the data face. No third family is introduced — including for code, which uses the data face inverted.

**The No-Kicker Rule.** No eyebrow, kicker, or small uppercase label sits above a heading or a display number. Section headings are preceded only by an index numeral on the same baseline, and the label that names a track sits *beside* the material, never above the number. Uppercase labels exist in this system; a label used as a decorative pre-heading does not.

**The Tracking Ladder Rule.** Letter-spacing rises as size falls: `-.01em` at display, `.02em` at body, `.10–.18em` at label and micro. Wide tracking is how small uppercase type stays legible — it is not an ornament and is never applied at body size or above.

## Layout

One centred column, `max-width: 1600px`, `padding: 0 16px 80px` — wide because this is a data surface, not an article. Vertical rhythm comes from sections: `padding: 34px 0` with a `hair-soft` bottom rule, so the page reads as stacked instrument panels rather than a scroll of content.

Spacing is a 4px unit (`--unit: 4px`) used mostly at 8 / 12 / 14 / 16 / 20 / 24. Panel interiors are 12–16px; gaps between sibling panels are 14px; the section-header-to-content gap is 20px.

The signature layout is the **dual track**: `grid-template-columns: minmax(0, 1fr) 260px, gap 24px, align-items: start`. The elastic left column carries measured material (tracks, poll stream); the fixed 260px right rail carries computed readouts. The rail's fixed width is what keeps inference visually subordinate to fact at every viewport above the breakpoint.

Secondary grids: scorecards and method columns both use `repeat(auto-fit, minmax(300px, 1fr))` / `minmax(260px, 1fr)` with 14–20px gaps, so column count is a function of available width rather than a set of hand-placed breakpoints. Event-log rows are a three-column grid (`120px minmax(0,1fr) auto`): fixed date, elastic interval bar, right-flushed gap figure.

**Responsive** — one breakpoint at `860px`. Below it: the dual track collapses to a single column; event rows stack; the sticky header becomes `position: static` (a sticky header at that height eats the viewport and lets content ghost through it) and the synthetic banner pins to `top: 0` in its place; nav wraps to a full-width third row at 9px with tightened tracking; the poll table gets its own `overflow-x: auto` with a `min-width: 540px` so it scrolls inside its panel instead of widening the page. The banner's offset is recomputed on resize against the header's measured height rather than a hard-coded value.

`prefers-reduced-motion: reduce` disables all animation and transition globally.

### Named Rules

**The Min-Width-Zero Rule.** Every child of a CSS grid in this system carries `min-width: 0`. Grid items default to `min-width: auto` and are pushed open by their widest content — a wide table inside a `1fr` column silently widened the whole section and, under `body { overflow-x: hidden }`, clipped the entire inference rail off-screen on mobile with no scrollbar to reveal it. Wide content scrolls inside its own panel; it never resizes its column.

**The Instrument Panel Rule.** Sections are numbered (`01`–`05`) and open with a three-part header on one baseline: index numeral, uppercase title, right-flushed lowercase note naming what the section is accountable for. A new section inherits this header or it does not belong on the page.

**The Fact-Left Rule.** Where fact and inference share a row, measured material takes the elastic column and computed material takes the fixed 260px rail. When the layout collapses, fact stacks first.

## Elevation & Depth

**There are no shadows in this system — not one `box-shadow` declaration exists in the build.** Depth is carried entirely by three flat devices: 1px hairline borders at two weights (`.22` structural, `.10` subordinate), opacity layering of white on black, and inversion. A panel is "raised" by being outlined, and only by being outlined.

Two real stacking layers exist: the fixed background barcode canvas at `z-index: 0` / `opacity: .5`, and the content shell at `z-index: 1`. Above the shell, the sticky header (`z-index: 5`) and synthetic banner (`z-index: 4`) both repaint an opaque ground so scrolled data never bleeds through them.

### Named Rules

**The No-Shadow Rule.** Surfaces never lift off the ground. If an element needs to separate from its neighbour, give it a hairline border; if it needs to dominate them, invert it. A shadow — especially a hard offset one — is foreign to this world and would read as a different instrument.

**The Two-Weight Hairline Rule.** Borders come in exactly two weights: `rgba(255,255,255,.22)` for anything that encloses, `rgba(255,255,255,.10)` for anything that merely divides. A third border tone is only admissible inside very dense tabular rows (`.06`), never as an enclosure.

## Shapes

Radius is zero everywhere: no element in the build declares `border-radius`. Every container, chip, tag, cell and bar is a hard rectangle, and the rectangle is the system's only silhouette. Corners meeting corners at 90° is the point — this is a plotted surface, not a card UI.

Form language runs at three scales of the same rectangle:
- **Bars**: 1px or 2px wide vertical strips at full container height, gapped 1px (barcode strips) or spaced pseudo-randomly across the viewport (canvas field). Width variance and opacity variance are the only texture.
- **Cells**: 11×11px squares in a 7-row grid with 2px gaps, outlined `hair-soft` when empty, filled solid white when lit, and marked by a 1px offset outline when "today". A miniature 5×5px / 2px-gap variant of the same grid appears inline in event rows.
- **Panels**: 1px-outlined rectangles with 12–16px padding, butt-joined where they belong together (the poll stream sits directly under the track panel with `border-top: 0`, so the two read as one instrument).

The single deviation from solid hairline is `border-style: dashed` on the "real state today" readout — the one panel describing a state the instrument has not yet measured. Dashed means *not yet real*; it is not a decorative variant and is used nowhere else.

### Named Rules

**The Zero-Radius Rule.** No element in this system has rounded corners, at any size, including chips, tags and inline code. A radius would soften a surface whose credibility comes from looking machined.

## Components

### Panels (hairline containers)
- **Character:** machined enclosures, not cards.
- **Shape:** 1px `hair` border, radius `0`.
- **Padding:** 12px (readout), 14px (track/card), 16px (verdict), 20px (pending state).
- **Background:** ground; no fill, no shadow.
- **Joined panels:** a continuation panel drops its `border-top` so the pair reads as one instrument face.
- **Dashed variant:** reserved for a panel describing an unmeasured state.

### Verdict Block (signature)
- **Character:** the one measured answer, and the only inverted display-scale surface on the page.
- **Style:** inverted (`#ffffff` ground, `#000000` ink), 16px padding, 1px border.
- **Type:** display face 800 at `clamp(20px, 3.4vw, 34px)`, uppercase, line-height 1.05; the key label above it sits at 10px `.18em` uppercase at `.7` opacity.
- **Foot:** a full-width 16px-tall barcode strip whose bars invert to black inside the block — the material follows the inversion.

### Track Chips
- **Style:** 10px uppercase, `.16em` tracking, 1px `hair` border, `1px 6px` padding, radius `0`.
- **`SOLID` (fact):** inverted — white fill, black text, border matched to fill.
- **`HAIRLINE` (inference):** outline only.
- The chip is never the sole carrier of the distinction; it accompanies the words FACT/INFERENCE in the same label.

### Synthetic Banner and Tags
- **Banner:** sticky, full-bleed, inverted, 10px `.14em` uppercase, `7px 16px` padding, led by a 40-bar barcode strip drawn in black. Its top offset is measured from the live header height.
- **Tag:** inline inverted block, 9px `.14em` uppercase, `1px 5px` padding, sitting beside a section heading.
- Both exist so no fabricated figure is ever on screen unlabelled.

### Readouts
- **Character:** the computed rail — quieter than fact by construction.
- **Structure:** 11px display-face heading, one headline number (26px display face, tabular) with its unit at 14px, a `.55`-opacity sentence, then a two-column `dl` (`1fr auto`) of term/value pairs — terms at 10px `.1em` uppercase `.55`, values right-flushed and tabular.
- **Caveat foot:** separated by a `hair-soft` top rule at 8px padding.

### Data Tables
- **Poll stream:** 10.5px, right-aligned except the first column, `.06` row rules, header row at 9px `.14em` uppercase `.45`. Body rows at `.72` opacity; the event row lifts to full opacity and 600 weight, and its verdict cell inverts.
- **Scorecards:** 11px, `hair-soft` row rules, first column at `.6` opacity, header at 10px uppercase `.5`.
- Absent values are written `NOT YET SCORED` or `—`, never a placeholder digit.

### Event Log Row
- **Shape:** 1px `hair` rectangle, `10px 12px` padding, three-column grid (`120px minmax(0,1fr) auto`), hover fills `rgba(255,255,255,.05)`.
- **Interval bar:** an 18px-tall axis with hairline left/right end-caps, a `hair-soft` centre line and three `hair-soft` six-hour ticks; the measured interval is a solid 8px white fill, `min-width: 2px`. An interval crossing midnight is drawn as two segments rather than overflowing.
- **Axis labels:** 00 / 06 / 12 / 18 / 24 at 9px, `.35` opacity, below the bar.

### Day Matrix
- **Cell:** 11×11px, 1px `hair-soft` outline, radius `0`. Lit = solid white fill with matching border. Out-of-range = transparent border. Today = 1px white outline at `+1px` offset.
- **Grid:** 7 rows (Monday first), column-flow, 2px gaps, with a month axis above and a weekday spine at left; scrolls horizontally inside its own wrapper.
- **Legend:** 10px `.12em` uppercase at `.6`, using the actual cell shapes as swatches.

### Navigation
- **Style:** 10px uppercase `.16em`, `.6` opacity, transparent 1px bottom border, no underline.
- **Hover / focus-visible:** opacity to `1` and the bottom border becomes white. Focus and hover are treated identically and both are always defined.
- **Mobile:** wraps to its own full-width row at 9px / `.1em`.

### Barcode Strip (signature material)
- **Character:** the fact material, used both as texture and as data.
- **Style:** flex row of 1px (72%) and 2px (28%) white bars with 1px gaps, each bar at full opacity or `.35`, generated from a seeded PRNG so the same strip renders identically on every load.
- **Inside an inverted block, the bars invert to black.**
- **Background field:** a full-viewport fixed canvas of the same material at `opacity: .5`, columns spaced 1–12px apart, alpha up to `.5`, seeded and drawn **once**.

### Named Rules

**The Three Materials Rule.** Solid bars mean measured. Hairline strokes mean computed. 0/1 cells mean per-day state. A new chart picks one of these three and inherits its meaning; introducing a fourth material redefines the vocabulary and must be a deliberate act, not a chart-library default.

**The Computed-Not-Typed Rule.** No published figure is typed into markup. Every number on the page — including the Weibull shape and scale, which are estimated in-page by method of moments — is derived at runtime from the single `EVENTS` array. A printed parameter that cannot reproduce the probability beside it is the defect this rule exists to prevent.

**The Honest Absence Rule.** Data that does not exist reads `NOT YET SCORED`, `INSUFFICIENT DATA`, or `—`. It never reads as a plausible number, a zero standing in for unknown, or an empty cell. Illustrative figures carry a `SYNTHETIC` tag on their section plus a sticky page banner.

**The One Authored Moment Rule.** Motion is not ambient. The background field is a static material: it is built and drawn once, redrawn only on resize (debounced 150ms), and carries no animation loop. The system's motion budget is reserved for a single authored moment — a newly detected reset inverting the field — which is specified but not yet wired. `prefers-reduced-motion: reduce` kills all animation and transition globally.

**The True-Scale Rule.** A mark's geometry reports its measurement. Interval bars are drawn at true axis scale and floored at 1.2 units only when the true width is sub-pixel, and the label says so; the hazard axis is scaled to the curve's own maximum so nothing is silently clipped against a fixed ceiling. Where geometry cannot carry the truth, the label carries it.

## Do's and Don'ts

### Do:
- **Do** build every tone from white at reduced opacity or hairline density on `#000000`. The two pigments are `#ffffff` and `#000000`.
- **Do** reserve inversion (white ground, black ink) for measured fact and for honesty apparatus (synthetic banner and tags).
- **Do** give fact and inference at least three simultaneous non-colour separators: material, an explicit `SOLID`/`HAIRLINE` chip, and the literal words FACT and INFERENCE.
- **Do** put `min-width: 0` on every grid child, and let wide tables scroll inside their own panel.
- **Do** set every figure with tabular numerals.
- **Do** compute every published number at runtime from the event data, including model parameters.
- **Do** write `NOT YET SCORED` / `INSUFFICIENT DATA` where a value does not exist, and tag any illustrative figure `SYNTHETIC`.
- **Do** open each section with index numeral, uppercase title, and a right-flushed accountability note on one baseline.
- **Do** define `:hover` and `:focus-visible` identically on every interactive element.

### Don't:
- **Don't** introduce a grey token or any hue — no green for good, no red for alert, no brand accent.
- **Don't** add a `box-shadow` of any kind; separation is a hairline, dominance is an inversion.
- **Don't** add `border-radius` to anything, at any size.
- **Don't** place an eyebrow, kicker, or decorative uppercase label above a heading or a display number.
- **Don't** introduce a third type family, or set body copy in Martian Mono.
- **Don't** run ambient or looping animation; motion belongs to a single authored event.
- **Don't** widen a mark beyond its true measured scale to make it visible — floor it, and say in the label that you did.
- **Don't** invent a fourth material to make a new chart type fit.
- **Don't** let a second inverted block share a screen with the verdict block without a reason; inversion is the entire emphasis budget.
