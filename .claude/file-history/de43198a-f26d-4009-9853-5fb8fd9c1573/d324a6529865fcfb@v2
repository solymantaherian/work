# Refactoring Notes: CLI Interface v1 → v2

## Summary

`cli_interface_v1.py` worked correctly but carried three structural problems in 64 lines: the
`summary` and `monthly` report branches were 13 lines of copy-pasted code differing only in a title
string, the three error branches repeated the same four-line banner, and 80 magic literals (including
`50` repeated 14 times across the border rules) were scattered through the two methods with no type
annotations anywhere. `cli_interface_v2.py` collapses the duplicated branches into table-driven
lookups, extracts the layout literals into 17 named class constants, splits the 24-statement
`display_report` into five focused formatters, and annotates every parameter and return. This is a
structure-only refactor: the public API, the error messages, and the rendered output are unchanged,
verified byte-for-byte against a golden capture of v1.

## Changes Applied

### 1. Extracted presentation literals to class constants

> **Deviation from the brief.** The task specified extracting ANSI color codes into
> `RESET`/`RED`/`GREEN`/`BLUE`/`YELLOW`. **v1 contains no color codes** — `grep '033\['` returns zero
> hits across the entire repository. Those five constants would have been dead code, and emitting
> real color would have violated the "output format must be EXACTLY the same" constraint. The
> analogous extraction that *does* have targets — the layout and character literals — was applied
> instead. Adding color is a behavior change and belongs in its own pass.

- **What**: Added 17 class constants covering layout (`LINE_WIDTH`, `LABEL_WIDTH`, `AMOUNT_WIDTH`,
  `AMOUNT_DECIMALS`, `INDENT`), characters (`BORDER_CHAR`, `DIVIDER_CHAR`, `ERROR_CHAR`,
  `CURRENCY_SYMBOL`), text (`TOTAL_LABEL`, `UNKNOWN_MODE`, `REPORT_TITLES`, three `ERROR_HEADING_*`),
  and classification (`FILE_ERROR_KEYWORDS`, `DATA_ERROR_KEYWORDS`). Every inline `"=" * 50`,
  `"!" * 50`, `:20s`, and `>10.2f` now derives from them.
- **Why**: `50` appeared 14 times (6× `"="`, 6× `"!"`, 2× `"-"`), and the widths were silently
  coupled — `2 + 20 + 1 + 1 + 10 = 34` had to stay under the 50-char border, but nothing expressed
  that. Changing the report width meant finding every one of the 14 sites by hand.
- **Benefit**: Magic literals in method bodies fell from **80 to 22 (-73%)**; magic numbers from
  **16 to 1**. Report width is now a one-line change.
- **Risk**: **LOW** — pure substitution. The one real hazard was the nested f-string format specs
  (`f"{amount:>{self.AMOUNT_WIDTH}.{self.AMOUNT_DECIMALS}f}"`), where an off-by-one in width or
  precision would shift every amount column.
- **Validation**: Golden diff covers wide amounts (`$1234567.89`), negatives (`$    -50.00`), zero
  (`$      0.00`), integers coerced to 2dp, and a 40-character label that overflows the column — all
  byte-identical.

### 2. Created `_format_error_message` helper

- **What**: Extracted the repeated four-line banner into
  `_format_error_message(msg: str, heading: str = ERROR_HEADING_GENERIC) -> str`, with heading
  selection split out into `_error_heading(error_str) -> str`. `display_error` is now 3 statements,
  down from 15.
- **Why**: All three branches printed an identical banner; only the heading differed. `"!" * 50`
  appeared 6 times in 15 lines.
- **Benefit**: `display_error` shrank **15 → 3 statements (-80%)**. Error presentation has one
  definition site, and classification became independently testable.
- **Risk**: **LOW** structurally, but the banner is newline-sensitive: v1 built it from four separate
  `print()` calls (leading `"\n" + border`, trailing `border + "\n"`), so consolidating into one
  string required getting the leading and trailing blank lines exactly right — an easy place to gain
  or lose a newline invisibly.
- **Validation**: Golden diff includes an empty-message error (which renders a trailing-space line)
  and a multi-line message (whose continuation is *not* indented) — both preserved exactly.

> **Signature note**: the brief specified `_format_error_message(msg: str) -> str`. The heading varies
> across the three error kinds while the banner does not, so the helper takes an optional second
> argument. It remains callable with one argument as specified.

### 3. Added complete type hints

- **What**: Annotated every parameter and return across all 7 methods, added a `ReportData`
  `TypedDict` (`total=False`, documenting that all keys are optional because v1 reads them with
  `.get()`), and annotated all 17 class constants.
- **Why**: Neither public method had any annotation. `report_data`'s shape was discoverable only by
  reading the `.get()` calls, and `display_error`'s accepted type was ambiguous — it calls
  `str(error)`, so it takes anything, and the tests pass three different exception types.
- **Benefit**: Type-hint coverage **0% (0/4 slots) → 100% (16/16 slots)**. Malformed report dicts are
  now catchable by a type checker at the call site.
- **Risk**: **LOW** — annotations are not enforced at runtime. The one judgement call was typing
  `display_error(error: Any)` rather than `BaseException`, because v1 accepts bare strings and
  narrowing would have misdescribed the existing contract.
- **Validation**: Golden case passes a plain string (`"a bare string, not an exception"`) — still
  renders correctly, confirming the permissive annotation matches real behavior.

### 4. Split `display_report` into focused methods

- **What**: Extracted `_format_header(title)`, `_format_row(label, amount)`, and
  `_format_footer(total)`, and replaced the duplicated `if mode == 'summary' / elif mode == 'monthly'`
  branches with a `REPORT_TITLES` dict lookup. The total row now reuses `_format_row`.
- **Why**: `display_report` was 24 statements across 31 lines doing four jobs — mode dispatch,
  formatting, I/O, and unknown-mode error handling — with 13 of those lines duplicated verbatim
  between the two branches.
- **Benefit**: `display_report` fell to **10 statements / 14 lines (-58%)**; no method in v2 exceeds
  10 statements. Adding a report type is now a one-line dict entry instead of a copy-pasted branch,
  and the two modes can no longer drift apart in formatting.
- **Risk**: **MEDIUM** — the highest-risk change. Each `print()` in v1 appended its own newline; the
  formatters return strings that `print()` then terminates, so the blank-line placement had to be
  reconstructed rather than copied. **The existing test suite could not have caught a regression
  here**: every assertion is a substring check (`'SUMMARY' in output.upper()`, `'150.50' in output`)
  and none pins spacing, widths, or rules. A silently mangled layout would have passed all 6 tests.
- **Validation**: This is why the golden capture was taken *before* any edit. 19 cases across both
  report modes and all error paths, diffed byte-for-byte — identical, md5 `acbe6dbe…` on both sides.

## Metrics Comparison

| Metric | v1 | v2 | Improvement |
|---|---|---|---|
| Magic literals in method bodies | 80 | 22 | **-58 (-73%)** |
| — magic numbers | 16 | 1 | -15 (-94%) |
| — magic strings | 64 | 21 | -43 (-67%) |
| Named constants | 0 | 17 | +17 |
| Type hint coverage | 0% (0/4) | 100% (16/16) | **+100pp** |
| Longest method (statements) | 24 (`display_report`) | 10 (`display_report`) | **-14 (-58%)** |
| Longest method (code lines) | 31 | 14 | -17 (-55%) |
| `display_error` (statements) | 15 | 3 | -12 (-80%) |
| Methods | 2 | 7 | +5 |
| Duplicated report branches | 2 × 13 lines | 0 | eliminated |
| Trailing-whitespace lines (W291/W293) | 9 | 0 | -9 |
| Total lines | 64 | 216 | +152 |
| — of which docstrings | 9 | 115 | +106 |
| — non-docstring lines | 55 | 101 | +46 |

**On the line count**: v2 is 3.4× longer, and that is the expected trade. 115 of the 152 added lines
are docstrings (a stated quality requirement); the remaining growth is the 17 constant definitions
and 5 method signatures. The metric that tracks actual complexity is statements per method, where the
longest method more than halved.

**Counting method**: magic literals are `ast.Constant` nodes inside method bodies, docstrings
excluded. v2's residual 21 strings are mostly f-string format-spec fragments (`'>'`, `'s'`, `'f'`,
`'.'`) that the AST splits out of nested specs, plus the `'mode'`/`'data'`/`'total'` dict keys — not
the repeated layout literals the refactor targeted. Type-hint coverage counts annotated slots
(one per non-`self` parameter, plus one return) over total slots.

## Testing

- **All original tests pass**: ✓ — 55 passed (49 package + 6 CLI), `test_cli_interface.py` unmodified
- **No behavior changes**: ✓ — 19-case golden capture diffed byte-for-byte, md5 `acbe6dbe…` identical
- **Backward compatible**: ✓ — `display_report(self, report_data)` and `display_error(self, error)`
  signatures unchanged, public surface still exactly those two methods, `CLIInterface()` still zero-arg

### Validation method

The test suite alone was insufficient — all 6 assertions are substring checks that do not pin output
format. Before editing, v1's exact output was captured across 19 cases:

| Category | Cases |
|---|---|
| Report modes | summary, monthly, unknown mode, missing `mode` key |
| Formatting edges | 40-char overflowing label, 7-figure amount, negative, zero, integer amounts, unsorted keys |
| Degenerate input | empty `data`, missing `data`/`total` keys |
| Error paths | `FileNotFoundError`, `ValueError`, generic `Exception`, bare string, empty message, multi-line message |
| Classification quirks | `ValueError("Invalid file path")`, `RuntimeError("record not found…")`, `Exception("FILE missing")` |

`test_cli_interface.py` prefers `cli_interface_v2` when present and falls back to v1, so the 6 CLI
tests now exercise v2 — confirmed by asserting the resolved module name rather than assuming it.

## Deliberately not changed

Three issues from the code review were left in place because fixing them would change behavior, which
the constraints excluded:

1. **Error classification is substring-based and order-dependent.** `ValueError("Invalid file path")`
   is headed "File Not Found" because `'file'` is tested before `'invalid'`. Reproduced exactly in
   `_error_heading`, with a docstring recording why. The fix is `isinstance`-based dispatch. Note
   that the tests cannot detect this either way — `'ERROR'` is a substring of all three headings.
2. **Missing keys render a plausible empty report.** `display_report({'mode': 'summary'})` prints a
   clean $0.00 report, so a broken pipeline is indistinguishable from a user with no expenses.
3. **`total` is never reconciled** against `sum(data.values())`.

Also out of scope: errors print to **stdout** here while `expense_tracker/cli.py` sends them to
stderr, and this module's mode vocabulary (`'summary'`) disagrees with the package's user-facing
choices (`'category'`, `'monthly'`, `'top'`) — a cross-module contract change that warrants its own
tests.
