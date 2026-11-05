# Accessibility review

Target: WCAG 2.2 level AA for the Rung pane inside Hermes Desktop. Every claim below is measured in the
running pane (Chromium inside Electron) by a test, not inferred from the source:

- `tests/e2e/test_uc20_accessibility.py`: keyboard journey, names in every view, dialog focus, contrast in
  four theme and mode combinations, reduced motion (UC20, ACC-01 to ACC-06).
- `tests/e2e/smoke/test_a11y_review.py`: target size, focus not obscured, text spacing.
- `tests/e2e/a11y.py`: the measuring helpers (accessibility tree names, computed colours composited over the
  real painted background, focus ring visibility).

Coverage by criterion:

- Keyboard (2.1.1, 2.1.2, 2.4.3): a whole build flow from a new need to a passing test by keyboard only;
  every clickable element is a native control or gets `role=button`, `tabIndex=0` and Enter/Space from the
  one element factory `h()` in `desktop/src/00-core.js`. No trap outside dialogs.
- Focus visible (2.4.7) and not obscured (2.4.11): a 2 px outline in the needs colour on `:focus-visible`;
  sixty Tab stops checked for a visible ring and for the focused element being the top element on screen.
- Names and roles (1.3.1, 4.1.2, 2.5.3): the accessibility tree is read in every view; inputs are named by
  their visible label; checkboxes and radios by the label that wraps them; dialogs have `role=dialog`,
  `aria-modal` and the dialog title as their name.
- Dialog focus (2.4.3): initial focus on the first field, Tab cycles inside, Escape closes, focus returns to
  the control that opened it (retire, delete, defect, conflict).
- Contrast (1.4.3, 1.4.11): status colours are fitted per theme to at least 4.5:1 against every surface they
  appear on (page, card, well, button, hover, status tint), measured on rendered pixels in light and dark.
- Use of colour (1.4.1): every status has its text label (Error, Unknown, Needs input, No change, Partial,
  Draft failed, Seen failing, Retired, Read only).
- Motion (2.3.3 at AAA, 2.2.2): `prefers-reduced-motion: reduce` stops every animation and transition in the
  pane; the test measures running animations with the preference on.
- Target size (2.5.8): every target is at least 24 by 24 CSS px or meets the spacing exception.
- Text spacing (1.4.12): with line height 1.5, letter spacing 0.12 em and word spacing 0.16 em forced, no
  button, heading or label clips its text in eight views.
- Status messages (4.1.3): the Needs you chip in the status bar is a polite live region; error lines and the
  edit conflict bar are alerts. Run and execution views update their status badge in place.

## Findings

| # | Criterion | Finding | Status | Reason |
| --- | --- | --- | --- | --- |
| A1 | 4.1.2 | Checkboxes and radios got a synthetic `aria-label` that overrode their visible label | fixed | The element factory no longer names checkboxes and radios; the wrapping label names them |
| A2 | 4.1.2 | Project status colour selectors and the numeric cost and max runs fields had no name | fixed | Named from the field label map in `desktop/src/00-core.js` |
| A3 | 1.4.3 | Status colours were fitted to the page background only and fell below 4.5:1 on cards, wells and tints | fixed | Fitted against every surface they are drawn on; UC20 contrast passes in four themes |
| A4 | 2.4.3 | The defect form was a bespoke modal without focus return | fixed | Uses the shared `Dialog`: initial focus, trap, Escape, focus return |
| A5 | 2.5.8 | Rail test rows were 16 px tall and 20 px apart, inside each other's 24 px circles | fixed | Rows padded to 24 px (`TreeTest`, `desktop/src/10-shell.js`) |
| A6 | 1.4.10 | Reflow at 320 CSS px is not measured | declined | The pane lives inside the Hermes Desktop window, whose minimum size and sidebar are set by Hermes, not by a plugin; the pane keeps the window's layout and wraps long text (worst-case smoke test). A plugin cannot change the window's minimum; narrow windows are an exploratory charter (Worst-case data) |
| A7 | 1.4.4 | Text resize to 200 percent is not measured separately | declined | Desktop zoom (Cmd plus) scales the whole window, including the pane, as one page zoom; the pane uses relative layout with no fixed heights on text containers, and the worst-case smoke test checks no view overflows the window with long text |
| A8 | 3.3.1 | Errors were not announced | fixed | Error lines and the conflict bar have `role=alert`; engine errors carry the field (`RungError.field`) and the pane shows the message under that field |
| A9 | 2.4.2 | Page titles | declined | The window title belongs to Hermes Desktop; each pane view has a heading and each dialog a title, which is what a plugin controls |
| A10 | 4.1.3 | The Needs you count changed silently | fixed | The status chip is a polite live region (`desktop/src/99-app.js`) |
