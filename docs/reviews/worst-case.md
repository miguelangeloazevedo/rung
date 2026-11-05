# Worst-case review

Procedure: the `break-ui` skill. The worst case enters through the same seams as the demo data: the engine
calls in `tests/support/seed.py` (`seed_large` with a `text` override), never hand-edited markup. The fixture
and the checks run in `tests/e2e/smoke/test_readiness_smoke.py::test_res07_sec03_worst_case_data_breaks_no_view`
on every readiness run, at the pane's real size (1440x900 Desktop window).

## Surface map

Values the pane renders, with their source and limit:

- Need, requirement, specification and test text: engine, user or agent text, unbounded.
- Ids (N-1, R-12, S-12.3, T-12.3a): engine, generated, grow with the ladder.
- Project name and folder: user, name unique, folder an absolute path, unbounded.
- Commands, pass rules, execution output: user and the test process; output is bounded when the command
  runs (`rung_engine/execute.py`, cut at a fixed limit and labelled).
- Reasons (retire, draft failed, needs input, error): user, worker or engine, unbounded.
- Counts (tiles, Needs you, coverage x of y, run and attempt numbers): engine, integers.
- Times and durations: engine clock, shown as day and clock or seconds and minutes.
- List lengths: needs, rungs in the rail, executions per test, projects, retired needs: unbounded, not paginated.

## Fixture

- Text: one value in five is 700 characters of words, one is Japanese, Latin accents, emoji and Arabic
  (right to left), one carries HTML that would run script if rendered (`<img onerror>`, `<b>`), one is a single
  300 character word, the rest are short.
- Huge: a project of 20 needs and 1,040 rungs with 1,200 recorded executions.
- One: a project with a single need whose title is the markup string.
- Empty: a project with nothing in it.

Every view in the feature map is opened for each project; a view fails on an error state, executed markup,
rendered markup, or any element wider than the window.

## Findings

| # | Severity | Field | Worst-case value | Status | Reason |
| --- | --- | --- | --- | --- | --- |
| W1 | Ugly | Rail need text | a 300 character unbroken word | fixed | The rail column now shrinks (`min-w-0`) and the pane breaks unbroken words (`overflow-wrap:anywhere`); before, the rail ran 1,460 px past the window |
| W2 | Broken | Test folder | `../..`, `/etc`, `~`, a symlink to outside | fixed | Refused on save with a field error, and at run time the resolved folder must stay inside the project folder; the execution is Error with the reason |
| W3 | Fragile | Truncated reasons, commands, rail lines | any long value | fixed | Each truncated value has its full text as a tooltip and in its own view |
| W4 | Held | Need text with HTML | `<img src=x onerror=...><b>` | declined | No change needed: React renders it as text; the test asserts the string is on screen as typed and nothing executed |
| W5 | Held | Right-to-left and emoji text | Arabic, Japanese, emoji | declined | No change needed: renders in place with no overflow in every view |
| W6 | Fragile | Rail length | 1,040 rungs | declined | Not virtualised: the full rail renders within two seconds (asserted) and engine reads stay under 20 ms at 500 rungs; virtualising would break find-in-page and the keyboard order. Revisit above 5,000 rungs |
| W7 | Fragile | Executions in a project | 1,200 recorded results | declined | Execution lists render in full; every view of this project stays within the window and loads without an error state. Paging would hide the history a read-out cites |
| W8 | Held | Empty project | no needs | declined | No change needed: each empty list shows its label and at most one action (UC13 and smoke `test_empty_states`) |
| W9 | Held | Execution output | a test printing megabytes | declined | No change needed: output is cut at a fixed limit while the command runs and the cut is labelled `[output truncated at N characters]` (`rung_engine/execute.py`) |
| W10 | Ugly | Delete confirm field | a long project name | fixed | The field shows the name as its placeholder, so the exact value is visible while typing |
