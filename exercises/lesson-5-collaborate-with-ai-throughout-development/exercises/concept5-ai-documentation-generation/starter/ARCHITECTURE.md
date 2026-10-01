# Architecture

Developer-facing design documentation for the Expense Tracker CLI. For user instructions, see [README.md](README.md).

> **Note on accuracy.** This document describes the code as it exists today, verified by reading and running it. Where the implementation diverges from its own docstrings or from the project's design intent, that gap is called out explicitly rather than papered over. See [Known Gaps](#known-gaps).

---

## Overview

Expense Tracker CLI is a batch pipeline: it reads expense records from a file, validates them into domain objects, aggregates them one of several ways, and prints the result. It runs once per invocation and holds no state between runs.

### Goals

| Goal | How the architecture serves it |
|------|-------------------------------|
| **Add report types without touching existing code** | Report strategies implement one interface and self-register in a factory |
| **Support other data sources later** | Loading sits behind a `TransactionLoader` abstraction, not a concrete CSV reader |
| **Fail clearly on bad data** | A typed exception hierarchy carries row numbers to the surface and maps to exit codes |
| **Stay dependency-free** | Standard library only — no install step, nothing to keep current |
| **Be correct about money** | `Decimal` everywhere; `float` never touches an amount |

### Design Principles

1. **Depend on abstractions.** The layers that orchestrate work talk to `TransactionLoader` and `ReportMode`, not to `CSVTransactionLoader` and `CategorySummaryReport`. (Partially realised — see [Known Gaps](#known-gaps).)
2. **Keep the domain at the centre.** `domain/` imports nothing from the rest of the package. Every other module depends inward toward it.
3. **Validate at the boundary.** Data is checked as it enters the system. Once a `Transaction` exists, it is valid by construction and immutable.
4. **Fail fast and loudly.** The loader aborts on the first bad row rather than silently skipping it, so a malformed file can't quietly produce a plausible-looking wrong total.
5. **One reason to change per module.** Parsing, aggregating, and presenting are separate concerns in separate packages.

---

## Architecture Diagram

### Layers and dependency direction

```
                        ┌───────────────────────────┐
                        │        main.py            │   entry point
                        │  (calls cli.main())       │
                        └─────────────┬─────────────┘
                                      │
                                      ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │                    expense_tracker/cli.py                        │
  │                     ExpenseTrackerCLI                            │
  │   • parses argv            • orchestrates the run                │
  │   • maps exceptions → exit codes                                 │
  └───────┬──────────────────────────────────────┬───────────────────┘
          │                                      │
          ▼                                      ▼
  ┌───────────────────────┐          ┌───────────────────────────────┐
  │   data/               │          │   reports/                    │
  │   transaction_loader  │          │   report_factory.py           │
  │                       │          │      ReportFactory            │
  │   TransactionLoader   │◄─ABC     │        │ creates              │
  │   └ CSVTransaction    │          │        ▼                      │
  │       Loader          │          │   report_mode.py              │
  │                       │          │      ReportMode        ◄─ABC  │
  │                       │          │      ├ CategorySummaryReport  │
  │                       │          │      ├ MonthlyTotalsReport    │
  │                       │          │      └ TopExpensesReport      │
  └───────────┬───────────┘          └───────────────┬───────────────┘
              │                                      │
              └──────────────────┬───────────────────┘
                                 ▼
                    ┌────────────────────────────┐
                    │   domain/                  │   ← depends on nothing
                    │   models.py    Transaction │     (stable core)
                    │   exceptions.py  error tree│
                    └────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │  presentation/formatters.py  —  NOT WIRED IN (see Known Gaps)    │
  └──────────────────────────────────────────────────────────────────┘
```

All arrows point inward toward `domain/`. There are no cycles.

### Data flow for one invocation

```
  $ python3 main.py examples/sample_expenses.csv --report monthly

   argv
     │
     ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 1. PARSE      ExpenseTrackerCLI._create_argument_parser  │
  │               argparse → file, report, top_n             │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 2. EXISTS?    Path(file).exists()                        │
  │               no → DataLoadError                  exit 1 │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 3. LOAD       CSVTransactionLoader.load()                │
  │               csv.DictReader → per-row validation        │
  │               bad row → ValidationError(row_number) exit 1│
  │               ──────────────────────────────────────────  │
  │               out: List[Transaction]   (validated)       │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 4. GUARD      empty list → EmptyDatasetError      exit 3 │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 5. SELECT     ReportFactory.create_report('monthly')     │
  │               registry lookup → MonthlyTotalsReport()    │
  │               unknown → InvalidReportTypeError    exit 2 │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 6. AGGREGATE  report.process_transactions(transactions)  │
  │               group → sum → sort → format to str         │
  └──────────────────────────┬──────────────────────────────┘
                             ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 7. EMIT       print(output) → stdout              exit 0 │
  │               errors → stderr                            │
  └─────────────────────────────────────────────────────────┘
```

**The key seam is step 3 → step 6.** Reports never see CSV rows, files, or strings from disk — only `List[Transaction]`. That is what makes loaders and reports independently replaceable.

### Import graph

Verified against the source:

```
main.py                      → cli
cli.py                       → data.transaction_loader, reports.report_factory, domain.exceptions
data/transaction_loader.py   → domain.models, domain.exceptions
reports/report_factory.py    → reports.report_mode, domain.exceptions
reports/report_mode.py       → domain.models, domain.exceptions
domain/models.py             → (nothing internal)
domain/exceptions.py         → (nothing internal)
presentation/formatters.py   → (nothing internal, and nothing imports it)
```

---

## Design Patterns

### Strategy — report generation

**Where:** `reports/report_mode.py`. `ReportMode` is the strategy interface; `CategorySummaryReport`, `MonthlyTotalsReport`, and `TopExpensesReport` are the concrete strategies.

**The contract** is two methods:

```python
def process_transactions(self, transactions: List[Transaction]) -> str
def get_report_name(self) -> str
```

**Why this pattern.** The three reports differ only in *how they group and present the same input*. Without Strategy, that variation collapses into a conditional in the orchestrator that grows a branch per report type, and every new report means editing a function that already works. With Strategy, the variation lives in separate classes and the orchestrator holds one polymorphic call.

**What it buys this project:**
- A new report is a new file. No existing file's logic changes.
- Each report is unit-testable against a hand-built `List[Transaction]` with no file I/O.
- `TopExpensesReport` carries its own `top_n` state in `__init__` without any other report knowing that parameter exists.

**The trade-off:** returning a preformatted `str` means aggregation and presentation are fused. A report can't currently be rendered as JSON or CSV without rewriting it. See [Design Decisions](#design-decisions).

### Factory + Registry — report selection

**Where:** `reports/report_factory.py`.

`ReportFactory` holds a class-level dict mapping a CLI name to a strategy class:

```python
_registry: Dict[str, Type[ReportMode]] = {
    'category': CategorySummaryReport,
    'monthly':  MonthlyTotalsReport,
    'top':      TopExpensesReport,
}
```

**Why.** Something must turn the string `'monthly'` into an object. Putting that mapping in one place keeps the string-to-class knowledge out of the CLI, and `register_report()` lets code outside the package add a strategy at runtime without editing the registry literal.

**Public interface:**

| Method | Purpose |
|--------|---------|
| `create_report(report_type, **kwargs)` | Look up and instantiate; `**kwargs` forwards constructor args like `top_n` |
| `get_available_types()` | Sorted list of registered names — useful for help text and validation |
| `register_report(name, cls)` | Add a strategy; rejects duplicate names and non-`ReportMode` classes |

> This pattern is central to the design but is **not** mentioned in the project's own design notes. It is the primary extension point.

### Abstract Base Classes — contracts

**Where:** `ReportMode` and `TransactionLoader`, both via `abc.ABC` with `@abstractmethod`.

**Why ABCs rather than duck typing or `Protocol`:** instantiating an incomplete subclass raises `TypeError` immediately, at construction, naming the missing methods. A half-implemented report fails at startup rather than at the point of use, and the base class is also where the shared docstring contract lives — what to raise, what the return value must look like.

`ReportFactory.register_report()` leans on this directly: `issubclass(strategy_class, ReportMode)` is a cheap, reliable gate that structural typing would not give.

### Template Method — loader validation

**Where:** `CSVTransactionLoader._validate_and_create_transaction()`.

`load()` handles file mechanics — existence, encoding, CSV structure, header columns — and delegates per-row validation to a separate private method. A subclass can override row validation (to accept a different date format, say) without touching file handling.

### Immutable Value Object — `Transaction`

**Where:** `domain/models.py`.

`@dataclass(frozen=True)` with validation in `__post_init__`. Frozen gives hashability and safe sharing: reports sort and group the same list without any chance of mutating it for the next consumer. Validation in `__post_init__` means **a `Transaction` that exists is valid** — no report needs a defensive check.

---

## Module Descriptions

### `main.py` — entry point

**Responsibility:** the executable shim. Imports `cli.main` and calls it under `if __name__ == '__main__'`.

**Depends on:** `expense_tracker.cli`.

**Why it's separate:** it keeps the launchable script trivial so the real CLI logic stays importable and testable. Nothing here needs a test.

---

### `expense_tracker/cli.py` — argument parsing and orchestration

**Responsibility:** three jobs — define the command-line surface, run the pipeline in order, and translate exceptions into exit codes.

**Public interface:**

| Member | Purpose |
|--------|---------|
| `ExpenseTrackerCLI()` | Builds the argument parser on construction |
| `.run(args=None) -> int` | Executes the pipeline, returns an exit code. Accepts an args list, which makes it testable without touching `sys.argv` |
| `.parser` | The configured `argparse.ArgumentParser` |
| `main() -> NoReturn` | Console-script wrapper: `sys.exit(cli.run())` |

**Exit codes**, mapped in the `except` chain at the bottom of `run()`:

| Code | Raised by | Meaning |
|------|-----------|---------|
| `0` | — | Success |
| `1` | `DataLoadError`, `ValidationError`, unexpected `Exception` | File missing/unreadable, or bad data |
| `2` | `InvalidReportTypeError`, argparse | Bad arguments |
| `3` | `EmptyDatasetError`, other `ExpenseTrackerError` | Nothing to report on |
| `130` | `KeyboardInterrupt` | Ctrl-C (standard SIGINT convention) |

**Depends on:** `CSVTransactionLoader`, `ReportFactory`, the exception hierarchy.

**Extension points:** add a flag in `_create_argument_parser()`; add a pipeline step in `run()`. Note that `run()` is currently the only orchestrator — there is no separate engine class.

> **Gap:** `run()` instantiates `CSVTransactionLoader()` directly, so the loader cannot be swapped without editing this file. The class docstring claims "Follows Dependency Injection" — it does not, for the loader. See [Known Gaps](#known-gaps).

---

### `expense_tracker/domain/models.py` — domain types

**Responsibility:** define what a transaction *is*, and enforce it.

**Public interface:**

| Member | Notes |
|--------|-------|
| `Transaction` | Frozen dataclass: `date: date`, `amount: Decimal`, `category: str`, `description: str` |
| `ValidationResult` | Frozen result object with `.success()` / `.failure()` constructors |

`Transaction.__post_init__` rejects non-positive amounts and blank category/description, raising `ValueError`.

**Depends on:** nothing internal. This is the stable core.

> `ValidationResult` is defined but currently unused — validation raises exceptions instead of returning result objects. It is scaffolding for a future accumulate-all-errors mode.

---

### `expense_tracker/domain/exceptions.py` — error taxonomy

**Responsibility:** one exception type per failure mode, all under a common root so callers can catch broadly or narrowly.

```
Exception
└── ExpenseTrackerError          ← catch-all for the package
    ├── DataLoadError             source unreachable/unreadable/empty
    ├── ValidationError           bad data; carries .row_number
    ├── InvalidReportTypeError    unknown report; carries .report_type, .available_types
    └── EmptyDatasetError         nothing to aggregate
```

Two of these carry structured context rather than only a message:

- `ValidationError(message, row_number=None)` prefixes `"Row {n}: "` when a row number is given — this is why user-facing errors point at an exact line.
- `InvalidReportTypeError(report_type, available_types)` composes its own message listing valid options.

**Depends on:** nothing.

**Extension point:** subclass `ExpenseTrackerError` for a new failure mode, then add an `except` clause in `cli.run()` to assign it an exit code. Without that clause it falls through to the generic handler and exits `1`.

---

### `expense_tracker/data/transaction_loader.py` — input boundary

**Responsibility:** turn an external source into `List[Transaction]`, or raise.

**Public interface:**

| Member | Purpose |
|--------|---------|
| `TransactionLoader` (ABC) | Contract: `load(source)`, `validate_source(source)` |
| `CSVTransactionLoader` | CSV implementation |
| `CSVTransactionLoader.REQUIRED_COLUMNS` | `{'date','amount','category','description'}` |

**How `load()` behaves:**

1. Rejects a missing path or non-file with `DataLoadError`.
2. Rejects an empty file with `DataLoadError` (reads one byte, then seeks back).
3. Parses with `csv.DictReader` — **columns are matched by header name, so order is irrelevant and extra columns are ignored.**
4. Rejects a header missing any required column with `ValidationError`.
5. Validates each row, numbering from 2 so numbers line up with a spreadsheet.
6. Wraps `PermissionError`, `UnicodeDecodeError`, `csv.Error`, and `OSError` as `DataLoadError`.

Per-row validation strips whitespace, rejects empty fields, parses the date as ISO-8601, parses the amount as `Decimal`, and rejects non-positive amounts.

**Depends on:** `Transaction`, `DataLoadError`, `ValidationError`.

**Extension points:** subclass `TransactionLoader` for a new source (see [Adding a data source](#how-to-add-a-new-data-source)); override `_validate_and_create_transaction()` to change row rules.

---

### `expense_tracker/reports/report_mode.py` — aggregation strategies

**Responsibility:** turn `List[Transaction]` into a display-ready string.

| Class | Grouping key | Sort order | Extra state |
|-------|--------------|------------|-------------|
| `CategorySummaryReport` | `transaction.category` | Total, descending | — |
| `MonthlyTotalsReport` | `date.strftime('%Y-%m')` | Month, ascending | — |
| `TopExpensesReport` | none (per-transaction) | Amount, descending | `top_n` (default 10, must be ≥ 1) |

All three share a shape: guard against an empty list with `EmptyDatasetError`, aggregate with `defaultdict`, compute totals with `Decimal`, then build a list of lines and `'\n'.join()` it. `TopExpensesReport` additionally truncates descriptions over 30 characters to `27 chars + '...'` and appends a note when fewer transactions exist than requested.

**Depends on:** `Transaction`, `EmptyDatasetError`.

**Extension point:** subclass `ReportMode`. This is the most common change to this codebase.

---

### `expense_tracker/reports/report_factory.py` — strategy registry

Covered under [Factory + Registry](#factory--registry--report-selection). Depends on the three concrete reports and `InvalidReportTypeError`.

---

### `expense_tracker/presentation/formatters.py` — formatting helpers (not wired in)

**Intended responsibility:** reusable terminal formatting — `format_currency`, `format_table`, `format_separator`, `format_header`, `format_summary_line`, `truncate_text`.

**Actual status:** **nothing in the codebase imports this module.** Each report formats its own output inline with f-strings, duplicating the currency and truncation logic that lives here. `format_table()` raises `NotImplementedError`; the other five functions are implemented and working.

This module is the natural place to remove the formatting duplication across the three reports — but doing so requires implementing `format_table()` first. See [Known Gaps](#known-gaps).

---

## Adding New Features

Both walkthroughs below were executed against this codebase and produce the output shown.

### How to add a new report type

We'll add a `weekday` report that totals spending by day of the week.

#### Step 1 — Implement the strategy

Create `expense_tracker/reports/weekday_report.py`:

```python
"""Weekday totals report: groups transactions by day of the week."""

from collections import defaultdict
from typing import List

from expense_tracker.domain.exceptions import EmptyDatasetError
from expense_tracker.domain.models import Transaction
from expense_tracker.reports.report_mode import ReportMode


class WeekdayTotalsReport(ReportMode):
    """Groups transactions by day of the week."""

    DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
            'Friday', 'Saturday', 'Sunday']

    def process_transactions(self, transactions: List[Transaction]) -> str:
        if not transactions:
            raise EmptyDatasetError("Cannot generate report from empty transaction list")

        buckets = defaultdict(list)
        for t in transactions:
            buckets[t.date.weekday()].append(t.amount)

        lines = ["Weekday Totals Report", "=" * 50]
        lines.append(f"{'Day':<15} {'Total':>12} {'Count':>8}")
        lines.append("-" * 50)
        for idx in range(7):
            if idx in buckets:
                amounts = buckets[idx]
                lines.append(f"{self.DAYS[idx]:<15} ${sum(amounts):>11,.2f} {len(amounts):>8}")
        return '\n'.join(lines)

    def get_report_name(self) -> str:
        return "Weekday Totals"
```

Three rules the base class enforces or expects:
- Implement **both** abstract methods, or instantiation raises `TypeError`.
- Raise `EmptyDatasetError` on an empty list — the other reports do, and the CLI maps it to exit code 3.
- Sum with `Decimal`. The amounts arrive as `Decimal`; don't convert to `float`.

#### Step 2 — Register it

Add one line to `_registry` in `reports/report_factory.py`:

```python
_registry: Dict[str, Type[ReportMode]] = {
    'category': CategorySummaryReport,
    'monthly':  MonthlyTotalsReport,
    'top':      TopExpensesReport,
    'weekday':  WeekdayTotalsReport,   # ← add this (and the import)
}
```

Or register at runtime without editing the file:

```python
from expense_tracker.reports.report_factory import ReportFactory
ReportFactory.register_report('weekday', WeekdayTotalsReport)
```

#### Step 3 — Expose it on the command line ⚠️

**Registering is not enough.** `cli.py` hardcodes the valid report names in its argument parser:

```python
choices=['category', 'monthly', 'top'],
```

A registered-but-unlisted report is rejected before the factory is ever consulted:

```
main.py: error: argument --report: invalid choice: 'weekday'
         (choose from 'category', 'monthly', 'top')
```

So either add `'weekday'` to that list, or — better — delete the duplication by deriving the choices from the registry:

```python
choices=ReportFactory.get_available_types(),
```

With that change the CLI picks up any registered report automatically. One ordering caveat: `argparse` captures `choices` when the parser is built, so runtime registration must happen **before** `ExpenseTrackerCLI()` is constructed.

#### Step 4 — Run it

```bash
python3 main.py examples/sample_expenses.csv --report weekday
```

```
Weekday Totals Report
==================================================
Day                    Total    Count
--------------------------------------------------
Monday          $     660.50        3
Tuesday         $     630.00        2
Wednesday       $     270.50        5
Thursday        $     142.50        2
Friday          $     120.00        2
Saturday        $     217.73        4
Sunday          $     202.30        2
```

#### Step 5 — Test it

Reports are the easiest thing here to test, because they take plain objects and return a plain string:

```python
from datetime import date
from decimal import Decimal
from expense_tracker.domain.models import Transaction

def test_weekday_groups_by_day():
    txns = [
        Transaction(date(2025, 1, 6), Decimal('10.00'), 'Food', 'Mon lunch'),
        Transaction(date(2025, 1, 13), Decimal('15.00'), 'Food', 'Mon lunch'),
    ]
    output = WeekdayTotalsReport().process_transactions(txns)
    assert 'Monday' in output
    assert '25.00' in output
```

---

### How to add a new data source

We'll add a JSON loader. The report layer needs no changes at all — it only ever sees `List[Transaction]`.

#### Step 1 — Implement `TransactionLoader`

```python
"""JSON transaction loader."""

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List

from expense_tracker.data.transaction_loader import TransactionLoader
from expense_tracker.domain.exceptions import DataLoadError, ValidationError
from expense_tracker.domain.models import Transaction


class JSONTransactionLoader(TransactionLoader):
    """Loads transactions from a JSON array of objects."""

    def load(self, source: str) -> List[Transaction]:
        path = Path(source)
        if not path.exists():
            raise DataLoadError(f"File not found: {source}")
        try:
            records = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise DataLoadError(f"Invalid JSON in {source}: {e}") from e

        transactions = []
        for i, rec in enumerate(records, start=1):
            try:
                transactions.append(Transaction(
                    date=date.fromisoformat(rec['date']),
                    amount=Decimal(str(rec['amount'])),
                    category=rec['category'],
                    description=rec['description'],
                ))
            except (KeyError, ValueError, InvalidOperation) as e:
                raise ValidationError(str(e), row_number=i) from e
        return transactions

    def validate_source(self, source: str) -> bool:
        p = Path(source)
        return p.exists() and p.is_file()
```

**Contract obligations:**

| Obligation | Why |
|------------|-----|
| Return `List[Transaction]` | Reports depend on this type, nothing else |
| Raise `DataLoadError` for unreachable sources | CLI maps it to exit code 1 |
| Raise `ValidationError` for bad records | Pass `row_number` so the user can find the record |
| Never return partially-valid data | A `Transaction` that exists must be valid |
| `validate_source()` must not raise | It returns `False` on any problem |

Amounts are passed through `str()` before `Decimal` — `Decimal(0.1)` from a JSON float inherits binary floating-point error, while `Decimal('0.1')` is exact.

#### Step 2 — Wire it in

The integration point is `cli.py:run()`, which currently hardcodes:

```python
loader = CSVTransactionLoader()
```

The minimal approach is to select on file extension:

```python
suffix = file_path.suffix.lower()
if suffix == '.json':
    loader = JSONTransactionLoader()
else:
    loader = CSVTransactionLoader()
```

A cleaner approach mirrors the report design — a `LoaderFactory` with the same registry shape, keeping `cli.py` free of loader-specific knowledge. Better still, accept the loader as a constructor argument so tests can inject a fake:

```python
class ExpenseTrackerCLI:
    def __init__(self, loader: TransactionLoader | None = None):
        self.loader = loader or CSVTransactionLoader()
        self.parser = self._create_argument_parser()
```

That last change is what would make the class's "Dependency Injection" docstring true.

#### Step 3 — Verify

```python
from expense_tracker.reports.report_factory import ReportFactory

txns = JSONTransactionLoader().load('expenses.json')
print(ReportFactory.create_report('category').process_transactions(txns))
```

Every existing report works on the result unchanged — which is the payoff of the abstraction.

---

## Design Decisions

### Why Strategy for reports

**Alternatives considered:** a conditional chain in the orchestrator; a single report class with a `mode` parameter; separate top-level functions.

**Rejected because:** the conditional chain forces every new report to modify working code, and the branch count grows without bound. The `mode` parameter produces one class with three unrelated responsibilities and a constructor that means different things depending on the mode — `top_n` is meaningless for a category report.

**Chosen because** report types are the axis this project is most likely to grow along, and Strategy makes that growth additive. `TopExpensesReport` demonstrates the payoff: it carries constructor state (`top_n`) that no other report knows about, which a shared-class design would have to handle with an ignored parameter.

**Trade-off accepted:** three small classes with similar aggregate-and-format shapes instead of one function with a switch. The duplication is real — all three build lines with near-identical f-strings — and the cure is a shared formatting helper (`presentation/formatters.py`), not abandoning the pattern.

### Why ABCs instead of duck typing or `Protocol`

**Chosen because** of *when* the failure surfaces. Subclassing `ReportMode` and forgetting `get_report_name()` raises `TypeError` at instantiation, naming the missing method. With duck typing the same mistake surfaces as an `AttributeError` deep in a call stack, possibly after the expensive load has already run.

ABCs also give `register_report()` a reliable runtime check — `issubclass(cls, ReportMode)` — that `Protocol` cannot provide without `runtime_checkable`, and even then only by method-name matching.

**Trade-off:** inheritance is more rigid than structural typing, and the contract can't be satisfied by a class that isn't willing to inherit. For a small closed codebase with two extension points, the early, clear failure is worth more than the flexibility.

### Why the strategy returns `str`

`process_transactions()` returns a formatted string rather than structured data.

**In favour:** it's the simplest thing that works for a terminal tool. There's no separate rendering layer to keep in sync, and a report is fully testable by asserting on its output.

**Against:** aggregation and presentation are fused. Adding `--format json` or an HTML export means either rewriting every report or parsing strings back into data.

**If that need arrives,** the migration is: have strategies return a structured result (say, a list of row dicts plus a totals row), then move all the f-string formatting into `presentation/formatters.py` behind a renderer chosen at the CLI level. The `ReportMode` ABC is the single place that change is anchored.

### Why CSV rather than a database

**Chosen because** the data is small, user-owned, and hand-edited. A personal expense log is hundreds of rows a year — far below the point where indexed queries matter. CSV opens in any spreadsheet, diffs cleanly in version control, needs no schema migration, and survives this tool being abandoned.

A database would add a dependency or a schema-bearing file, an install step, and a migration story, in exchange for query speed nobody needs and durability CSV already has.

**Trade-off:** the whole file is loaded into memory and re-parsed on every run, and there's no way to query a subset without reading everything. For files under roughly 100,000 rows this is imperceptible. Because loading sits behind `TransactionLoader`, a SQLite backend could be added later without touching a single report.

### Why fail-fast loading

One invalid row aborts the entire load rather than being skipped with a warning.

**Chosen because** a silently skipped row produces a report that looks correct and is wrong — the worst possible outcome for a financial tool. A hard failure naming the row number is recoverable in seconds; a quietly understated total may never be noticed.

**Trade-off:** fixing a file with twenty bad rows takes twenty runs. `ValidationResult` in `domain/models.py` is unused scaffolding for a future accumulate-all-errors mode that would report every problem at once.

### Why `Decimal` rather than `float`

Binary floating point cannot represent most decimal fractions exactly — `0.1 + 0.2 == 0.30000000000000004`. Over hundreds of summed transactions the drift becomes visible in a printed total, and a money report that doesn't add up destroys trust in the tool. `Decimal` is exact for decimal arithmetic. Amounts are parsed straight from string to `Decimal`, never via `float`.

### Why validation lives in `__post_init__`

Putting the rules on the `Transaction` dataclass rather than in the loader means **every** construction path is validated — the CSV loader, a future JSON loader, and test fixtures alike. The loader layer adds parse-level checks (date format, numeric amount) with row-number context; the domain layer enforces the invariants that must hold regardless of source.

Consequence: reports never validate. If a `Transaction` exists, its amount is positive and its fields are non-empty.

---

## Testing Strategy

### Current state — read this first

The suite reports **55 passed, 6 skipped**, but that number is misleading:

```
tests/test_cli.py                     9 stubs,   0 implemented
tests/test_csv_loader.py              9 stubs,   0 implemented
tests/test_models.py                  9 stubs,   0 implemented
tests/test_report_factory.py          9 stubs,   0 implemented
tests/test_report_modes.py           13 stubs,   0 implemented
tests/test_documentation_quality.py   0 stubs,  12 implemented
─────────────────────────────────────────────────────────────
TOTAL                                49 stubs,  12 implemented
```

**49 of 61 tests are empty `pass` bodies with `# TODO: Implement test` comments.** They pass because they assert nothing. Real coverage of application code is currently **zero** — the only executing assertions are in `test_documentation_quality.py`, which checks that documentation files exist and contain required sections.

The test *structure* is sound: the files, class names, and method names lay out exactly what should be covered. Treat the stubs as a specification to fill in, not as a safety net that exists.

```bash
python3 -m pytest tests/ -q          # run everything
python3 -m pytest tests/ -v          # see which are stubs
```

### Where tests live

| File | Covers | Level |
|------|--------|-------|
| `tests/test_models.py` | `Transaction` validation, immutability, `ValidationResult` | Unit |
| `tests/test_csv_loader.py` | Parsing, structural validation, error cases | Unit + fixtures |
| `tests/test_report_modes.py` | Each strategy's aggregation and formatting | Unit |
| `tests/test_report_factory.py` | Registry lookup, custom registration, error cases | Unit |
| `tests/test_cli.py` | End-to-end runs, exit codes, stdout/stderr routing | Integration |
| `tests/test_documentation_quality.py` | Docs exist and cover required sections | Meta |
| `tests/fixtures/` | CSV files for loader tests (`valid_expenses.csv` present) | Data |

### How each layer should be tested

The architecture makes each layer testable in a different, cheap way:

**Domain (`models.py`, `exceptions.py`)** — pure, no I/O. Construct directly and assert:

```python
with pytest.raises(ValueError):
    Transaction(date(2025, 1, 1), Decimal('-5'), 'Food', 'Refund')
```

**Reports (`report_mode.py`)** — take objects, return a string. **No mocking needed or wanted.** Build a small `List[Transaction]`, call `process_transactions()`, assert on substrings:

```python
txns = [
    Transaction(date(2025, 1, 15), Decimal('42.50'), 'Food', 'Lunch'),
    Transaction(date(2025, 1, 16), Decimal('35.00'), 'Food', 'Dinner'),
]
out = CategorySummaryReport().process_transactions(txns)
assert '77.50' in out
```

Assert on the numbers that prove the aggregation, not on exact column alignment — otherwise a cosmetic width change breaks a dozen tests.

**Loader (`transaction_loader.py`)** — needs real files. Prefer `tests/fixtures/*.csv` for stable cases and `tmp_path` for one-offs:

```python
def test_rejects_bad_date(tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("date,amount,category,description\n01/15/2025,42.50,Food,Lunch\n")
    with pytest.raises(ValidationError) as exc:
        CSVTransactionLoader().load(str(f))
    assert exc.value.row_number == 2
```

`ValidationError.row_number` is structured, so assert on the attribute rather than string-matching the message.

**Factory (`report_factory.py`)** — pure lookup. One caveat: `_registry` is **class-level mutable state**, so a test that calls `register_report()` leaks into later tests. Clean up:

```python
def test_register_custom(self):
    ReportFactory.register_report('custom', MyReport)
    try:
        assert isinstance(ReportFactory.create_report('custom'), MyReport)
    finally:
        ReportFactory._registry.pop('custom', None)
```

**CLI (`cli.py`)** — integration. `run()` accepting an args list is the key testability affordance: pass arguments directly instead of patching `sys.argv`.

```python
def test_missing_file_returns_one(self):
    assert ExpenseTrackerCLI().run(['no_such_file.csv']) == 1
```

Capture output with pytest's `capsys` (or `unittest.mock.patch` on `sys.stdout`, which `test_cli.py` already imports):

```python
def test_report_goes_to_stdout(capsys):
    ExpenseTrackerCLI().run(['examples/sample_expenses.csv'])
    assert 'Category Summary Report' in capsys.readouterr().out
```

### Mocking strategy

**Mock sparingly.** The layering means almost everything can be tested with real objects, and real objects catch real bugs:

| Layer | Approach | Mock? |
|-------|----------|-------|
| Domain | Direct construction | Never |
| Reports | Hand-built `List[Transaction]` | Never |
| Loader | Fixture files / `tmp_path` | Rarely — only for `PermissionError`, `OSError` |
| Factory | Real registry + cleanup | Never |
| CLI | Real components, real fixture files | Only to capture streams |

The one place a genuine fake earns its keep is testing CLI orchestration independently of file parsing — and that requires the constructor injection described in [Adding a data source](#step-2--wire-it-in), which the code doesn't support yet. It is a concrete argument for making that change.

Where you do need to simulate an unreachable file, patch the boundary rather than the logic:

```python
with patch('pathlib.Path.exists', return_value=False):
    assert ExpenseTrackerCLI().run(['whatever.csv']) == 1
```

### Suggested priority for filling in the stubs

1. `test_models.py` — no dependencies; establishes the invariants everything else assumes.
2. `test_report_modes.py` — highest logic density, easiest to test, no I/O.
3. `test_csv_loader.py` — most error paths; fixtures needed (several are referenced but absent).
4. `test_report_factory.py` — small, but registry cleanup matters.
5. `test_cli.py` — exit codes and stream routing, once the layers beneath are trusted.

---

## Known Gaps

Discrepancies between the code and its own documentation or apparent intent. None break the tool; all are worth knowing before you change something.

| # | Gap | Location | Impact |
|---|-----|----------|--------|
| 1 | **Dependency Injection is claimed but not implemented.** The class docstring says "Follows Dependency Injection (dependencies passed to methods)"; `run()` instantiates `CSVTransactionLoader()` directly. | `cli.py` | Loader can't be swapped or faked without editing `cli.py`. Fix: constructor injection. |
| 2 | **Report names are duplicated in two places.** `ReportFactory._registry` and the argparse `choices` literal are independent sources of truth. | `report_factory.py`, `cli.py` | A registered report is invisible to the CLI. Fix: `choices=ReportFactory.get_available_types()`. |
| 3 | **`presentation/formatters.py` is dead code.** Nothing imports it; `format_table()` raises `NotImplementedError`. | `presentation/` | Formatting logic is duplicated across all three reports instead. |
| 4 | **`ValidationResult` is unused.** Defined in the domain but never constructed — validation raises instead. | `domain/models.py` | Harmless; scaffolding for accumulate-all-errors validation. |
| 5 | **No orchestration layer.** Design notes reference a `ReportEngine` that coordinates loader and report; no such class exists. `ExpenseTrackerCLI.run()` does the coordinating. | `cli.py` | Orchestration is coupled to the CLI and can't be reused by another front end. |
| 6 | **No packaging metadata.** No `setup.py`, `pyproject.toml`, or `requirements.txt`. | project root | The package imports only when the project root is the working directory. Running tests or scripts from elsewhere needs `PYTHONPATH=.`. |
| 7 | **Documentation tests point outside the project.** `test_documentation_quality.py` reads `../solution/README.md` and `../solution/ARCHITECTURE.md`, not the project's own copies. | `tests/` | Four architecture tests skip regardless of what exists here. |
| 8 | **Python version is understated.** The README previously claimed 3.8+; `X \| Y` annotations evaluated at import require **3.10+**. | `cli.py`, `exceptions.py`, `formatters.py` | Corrected in the README. |

---

## Quick Reference

### Where to make a change

| I want to… | Go to |
|------------|-------|
| Add a report type | New class in `reports/`, register in `report_factory.py`, add to `choices` in `cli.py` |
| Add a data source | New `TransactionLoader` subclass in `data/`, wire into `cli.run()` |
| Change CSV validation rules | `CSVTransactionLoader._validate_and_create_transaction()` |
| Change what makes a transaction valid | `Transaction.__post_init__()` |
| Add a command-line flag | `ExpenseTrackerCLI._create_argument_parser()` |
| Change an exit code | The `except` chain in `ExpenseTrackerCLI.run()` |
| Add an error type | Subclass `ExpenseTrackerError`, add an `except` clause in `run()` |
| Change report column layout | The relevant class in `report_mode.py` (not `formatters.py` — it isn't wired in) |

### Invariants to preserve

1. `domain/` imports nothing from the rest of the package. Keep it that way.
2. Money is `Decimal`, end to end. Never `float`.
3. A constructed `Transaction` is a valid one.
4. Reports receive `List[Transaction]` — never file paths, rows, or raw strings.
5. Errors raised inside the package derive from `ExpenseTrackerError`.
6. Failures are loud. Never skip a bad row silently.
