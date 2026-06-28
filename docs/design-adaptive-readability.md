# Design: adaptive readability (worst-case global model)

Status: approved for build (global design + SCK backdrop upgrade). Overlay deferred.

This document captures the design for term-chameleon's readability adaptation, after a
multi-agent research pass and an adversarial spike on the per-region ideal. It is the plan
of record; build work follows the phases below.

## The goal

Keep terminal text readable against whatever shows through a translucent ("glass") iTerm2
window, while preserving the glassy feel. Three failure modes motivated the work:

- A. Global brightness mismatch — bright/dark backdrop washes out fixed-palette text.
- B. Transparency as a controlled variable — as translucent as possible without dropping
  text below a readability floor.
- C. Local per-color collision — a specific glyph color over a similar-colored backdrop
  patch is unreadable even when the global average looks fine.

## The binding constraint (why the design is "global", not "per-region")

The literal per-region ideal — correct each glyph against the specific backdrop behind it —
is not achievable through any terminal's own controls. The wall is **actuation, not
observability**:

- Observability is solvable: macOS ScreenCaptureKit can capture everything *except* the
  terminal window, recovering the true pre-composite backdrop.
- Actuation is the wall: every response lever a terminal exposes (palette, transparency,
  blur, minimum-contrast) is a single session-wide value. Even with perfect per-cell
  knowledge you can only choose one global palette.

This is a macOS composition fact, not an iTerm2 quirk: the WindowServer owns the blur/
vibrancy backdrop and composites the app over it, so no app — including Ghostty/Kitty GPU
shaders — ever receives the backdrop pixels. The only path to true per-region correction is
an app-owned overlay window that *occludes* the backdrop locally; it is research-grade,
macOS+iTerm2-only, and at real text density its scrims tile into a near-opaque panel that
erases the glass the product exists for. Deferred to an optional, opt-in spike — never default.

## Levers we actually have (all already wired in iterm_api.py / osc.py)

- `set_transparency` (0..1) — the primary, guaranteed remedy. Lower it and every cell's
  effective background moves toward the opaque theme background; pushed far enough it clears
  any collision (the terminal-domain subtitle scrim).
- `set_minimum_contrast` (0..1) — iTerm2's built-in per-glyph foreground fixer. Necessary
  insurance, not sufficient: it anchors to the *theme* background, blind to the see-through
  backdrop. Calibrated empirically (iTerm2 brightness scale, not WCAG).
- `set_blur` / `set_blur_radius` — low-pass homogenizer; collapses local backdrop variance
  toward its mean. Secondary/aesthetic nudge.
- "Only the default BG color uses transparency" profile key — keeps empty space glassy while
  colored cells render opaque (prevents colored-cell bleed-through).
- 16-color palette + default fg/bg/cursor (API and OSC).
- `async_get_screen_contents` / `style_at` — detect which ANSI colors are actually on screen
  (used only if Phase 3 is ever triggered).

## What the platform cannot do

- Recolor one specific cell (detection can be per-cell; every response is session-wide).
- Make Minimum Contrast see through glass (anchored to the theme background).
- Reach transparency/blur/minimum-contrast over OSC (OSC only does palette + default fg/bg/
  cursor) — the Python API is required for the valuable knobs.

## Contrast metric: keep WCAG 2 (APCA rejected, with reasons)

APCA (WCAG-3 candidate) is more correct in theory for thin light-on-dark glyphs, but rejected
as overengineering here: no single gate to swap (the WCAG ratio + 4.5/3.0 thresholds + ":1"
display are woven through 8+ modules), the official source carries a restrictive Myndex
license, and the tool already measures real rendered pixels (Otsu in text_contrast.py), which
captures the thin-glyph concern empirically. Revisit only behind a dedicated spike that first
resolves the license and the multi-module threshold migration.

## The design: worst-case background coordination

Stop trying to solve against the unobservable true backdrop; enforce a worst-case the way
subtitles and map labels do, using existing levers.

- A (global): keep the average-luminance + variance sample -> classify -> coarse preset with
  anti-thrash hysteresis (`watch.py` ModeSelector). Right altitude for a whole-profile choice.
- B (transparency): a screenshot-calibrated **preset ladder**, each rung pairing a
  transparency value with a matching minimum-contrast and blur, plus "only default bg uses
  transparency". Not a runtime solver (its target is unobservable) — auditable static rungs.
- C (collision): the existing `variance >= 0.08` branch routes a splotchy/colliding backdrop
  to a high-blur + lower-transparency + higher-min-contrast rung. Blur homogenizes, lowered
  transparency is the guaranteed clear, min-contrast is free insurance.

### Settled defaults

- Minimum-contrast always-on per rung (cheap insurance).
- "Only default bg uses transparency" ON (prevents colored-cell bleed-through).
- Contrast floor stays at WCAG 4.5 (do not diverge from what other a11y tools report).

## Build phases

### Phase 1 — Calibrated transparency / min-contrast / blur ladder (solves B)
Order presets into a glassiness ladder (most-translucent -> opaque); each rung pairs
transparency + minimum_contrast + blur_radius, screenshot-verified on real backgrounds. Add
the "only default bg uses transparency" key to the profile dict, setter_mappings, and the
generated live-adapter.

### Phase 2 — Validate the variance branch clears C; keep min-contrast as insurance
Confirm `variance >= 0.08` routes colliding backgrounds to the right rung; tune the threshold
and target rung against real wallpapers exhibiting green-on-green; screenshot-verify blur +
lowered transparency + min-contrast clears it, honoring the HIGH_RISK cooldown override.

### Phase 3 (OPTIONAL — gated by a demonstrated, reproducible failure only)
Only if a static collision provably survives Phase 2: detect present chromatic ANSI indices
via `style_at`, add them to the Preset model + setters, and nudge the LUMINANCE ONLY (never
hue) of the single offending index, re-checked with hysteresis. Last resort.

### Tier-1 accuracy upgrade — SCK true-backdrop capture (do alongside, worth it regardless)
Replace `screencapture -x` (composited grab) in `screenshot.py` with a ScreenCaptureKit
exclude-terminal capture so the global classifier samples the true backdrop, weighted by where
text sits. ~1 dep (pyobjc-framework-ScreenCaptureKit), ~100-200 lines, reuses the existing
Screen Recording permission.

DECISION REQUIRED before building Tier-1: on macOS Tahoe (26.x) a non-bundled pip CLI hits TCC
error -3801 (Screen Recording), which forces shipping a signed/notarized `.app` bundle. This
threatens the *current* screencapture approach too, so it must be confronted regardless — but
it is a meaningful packaging change. Options: (a) ship a signed `.app`; (b) keep the CLI and
document the Tahoe limitation; (c) gate SCK behind a capability check and fall back to
screencapture. To be decided before Tier-1 lands.

## Rejected (do not re-propose)

- APCA as the gate / dual-metric hybrid — cross-cutting cost + license risk for marginal gain.
- Closed-loop transparency solver — termination signal (contrast vs true backdrop) is
  unobservable; solves against a fiction.
- Per-region worst-case-contrast sampling in the live loop — no per-tile text/bg pair exists
  there; the variance branch already covers the case.
- Per-color palette auto-nudging as a feature — duplicates iTerm2 Minimum Contrast; needs a
  data model the tool deliberately omits. Spike-trigger only.
- Blur as the sole remedy — homogenizes locally only; no contrast guarantee; must fall back
  to lowering transparency.
- Other-terminal GPU shaders — OS-level dead end; no app receives backdrop pixels.

## Open questions

- Empirically calibrated minimum_contrast value per transparency rung (needs screenshot
  verification per rung; not analytically derivable from WCAG).
- Is `variance >= 0.08` the right trigger for the green-on-green class, or does it need a
  second statistic (per-channel chroma spread)?
- Does any reproducible static collision actually survive Phase 2? If not, Phase 3 is never built.
- The Tahoe signing/bundle decision above.
