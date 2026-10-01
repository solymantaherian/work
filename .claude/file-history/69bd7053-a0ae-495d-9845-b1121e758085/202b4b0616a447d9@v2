# Architecture Plan — CLI Expense Tracker

**Author role:** Senior Python developer, SOLID-first design
**Stack:** Python 3.8+, standard library only, CSV file storage
**Date:** 2026-09-30

---

## 1. Problem Statement

A command-line tool that reads expense transactions from a CSV file
(`date, amount, category, description`), runs a user-selected report mode over
them, and prints a formatted report to the terminal.

The dominant force on the design is **extensibility of report types**: report
modes are the part of the system expected to grow. Everything else (loading,
formatting, orchestration) is expected to stay roughly fixed. The architecture
should therefore make "add a report" a *pure addition* and make everything else
boring.

### Constraints

| Constraint | Consequence for the design |
|---|---|
| Standard library only | No pydantic/click/rich — hand-rolled validation, `argparse`, manual column formatting |
| Python 3.8+ | `typing.List`/`Dict` (not PEP 585 builtins), no `match`, no `|` unions in annotations |
| Max 200 lines per module | Forces one concept per file; each report mode gets its own module |
| Each module independently testable | No module may construct its own collaborators or touch `sys.argv`/`stdout` implicitly |
| Graceful error handling | A single error taxonomy, caught once at the CLI boundary |

---

## 2. Architectural Alternatives Considered

Three approaches were evaluated before settling on one.

### Alternative A — Single-Module Script

One `expense_tracker.py` containing argument parsing, CSV reading, an
`if mode == "category": ... elif mode == "monthly": ...` dispatch chain, and
`print()` calls inline.

**Advantages**
- Fastest to write; zero indirection; trivially readable at small size.
- No import graph to reason about, nothing to wire together.

**Disadvantages**
- Violates **Open/Closed**: every new report edits the dispatch chain and grows
  the same file — the file most likely to already have working code in it.
- Violates **Single Responsibility**: parsing, I/O, aggregation, and formatting
  share one namespace.
- Breaks the 200-line cap within about three report modes.
- Untestable without side effects: you cannot exercise aggregation logic without
  also touching the filesystem and stdout.

**Verdict:** Rejected. Fails two explicit requirements (OCP, 200-line cap).

---

### Alternative B — Layered Modules with Enum/Conditional Dispatch

Separate modules for loading, reporting, and display, but report selection is a
conditional chain or a `Mode` enum inside a single `reports.py`, with one
function per mode.

**Advantages**
- Genuine separation of concerns; loading and display become testable in isolation.
- Simpler than a full strategy hierarchy — no abstract base class to learn.
- Report functions are plain functions: easy to call directly in tests.

**Disadvantages**
- Still **Open/Closed–violating at the seam that matters**: adding a report means
  editing `reports.py` (add the branch) *and* the enum *and* the CLI choices list.
  Three edits to existing code per addition.
- No enforced contract between report modes. Nothing stops one mode from
  returning a list of rows and another a formatted string, so the display layer
  accretes special cases.
- `reports.py` becomes the module that grows without bound — the 200-line cap
  becomes a recurring refactor tax rather than a design property.

**Verdict:** Rejected. A real improvement over A, but it concentrates change in
exactly the place the requirements say must be closed to modification.

---

### Alternative C — Strategy Pattern + Registry, Layered Modules *(selected)*

Loading, processing, and display are separate layers. Each report type is a
class implementing a common `ReportMode` interface, living in its own module,
and self-registering into a registry keyed by CLI name. An orchestrating
`ReportEngine` wires loader → strategy → formatter without knowing any concrete
type.

**Advantages**
- **Open/Closed holds at the growth point.** Adding a report = add one file.
  No existing module is edited.
- Each report mode is small, independently testable, and independently
  deletable.
- The `ReportMode` contract forces every mode to return the same structured
  shape, so the display layer stays fixed and generic.
- Available modes are discoverable at runtime from the registry, so `--help`
  and CLI validation stay correct automatically.

**Disadvantages**
- More files and one extra indirection; a reader must follow the registry to
  find the concrete class.
- The registry needs the mode modules to be imported before lookup — an
  import-side-effect that must be handled deliberately (see §6.3), or it becomes
  the classic "my plugin didn't load" bug.
- Slight over-engineering if the tool truly only ever ships two reports.

**Verdict:** **Selected.** The extra indirection is small and bounded; the
extensibility payoff is exactly what the requirements ask for.

---

## 3. Selected Architecture

**Chosen approach: Alternative C — layered architecture with the Strategy
pattern for report modes and a registry for mode discovery.**

### Rationale

The requirements name Open/Closed and the Strategy pattern explicitly, and name
"easy to add/extend report modes" as a functional requirement. Alternative C is
the only option where adding a report touches zero existing files. It also
happens to be the option that keeps every module comfortably under 200 lines
*by construction* rather than by discipline, because the only unbounded axis of
growth (report count) maps onto new files rather than longer files.

The cost — one extra layer of indirection and a registry to keep populated — is
paid once and is well-understood.

### Layers

```
┌─────────────────────────────────────────────────────────┐
│  Presentation      cli.py, formatters.py                │  argv in, text out
├─────────────────────────────────────────────────────────┤
│  Orchestration     engine.py                            │  wires the pipeline
├─────────────────────────────────────────────────────────┤
│  Domain            models.py, interfaces.py,            │  pure logic,
│                    modes/*.py, registry.py              │  no I/O
├─────────────────────────────────────────────────────────┤
│  Data Access       loaders/csv_loader.py, validation.py │  filesystem, parsing
└─────────────────────────────────────────────────────────┘
```

Dependencies point **downward and inward only**. The domain layer imports
nothing from presentation or data access; it defines the interfaces that those
layers implement. That inversion is what makes every layer testable in isolation.

---

## 4. Module Design and Responsibilities

Each module has exactly one reason to change.

| Module | Responsibility | Reason to change |
|---|---|---|
| `main.py` | Entry point. Calls `cli.run(sys.argv[1:])`, maps the returned exit code to `sys.exit`. ~15 lines. | Never, realistically |
| `cli.py` | Parses arguments with `argparse`, builds the concrete loader and mode from the registry, invokes `ReportEngine`, catches `ExpenseTrackerError` and renders it as a friendly message + non-zero exit code. **The only module that knows about `argv` and exit codes.** | CLI surface changes |
| `engine.py` | `ReportEngine` — orchestrates the workflow: `loader.load(path)` → `mode.process_transactions(txns)` → return `Report`. Holds no business rules, only sequencing. Receives its collaborators via constructor injection. | Workflow sequence changes |
| `interfaces.py` | Abstract contracts: `TransactionLoader` (ABC) and `ReportMode` (ABC). Docstrings specify pre/postconditions and which exceptions each method may raise. **No implementations.** | A contract changes |
| `models.py` | Immutable domain types: `Transaction` (a `NamedTuple` or frozen dataclass with `date: date`, `amount: Decimal`, `category: str`, `description: str`), `ReportRow`, and `Report` (title + rows + total). No behavior beyond simple derived properties. | The domain vocabulary changes |
| `errors.py` | Exception hierarchy rooted at `ExpenseTrackerError`: `DataFileNotFoundError`, `MalformedDataError` (carries row number + offending field), `UnknownReportModeError`. Lets `cli.py` catch one base type. | A new failure category appears |
| `loaders/csv_loader.py` | `CsvTransactionLoader` — implements `TransactionLoader`. Opens the file with an explicit encoding and `newline=''`, reads via `csv.DictReader`, delegates per-row conversion to `validation.py`, raises the typed errors from `errors.py`. | CSV dialect / file handling changes |
| `loaders/validation.py` | Pure field coercion and validation: string → `date`, string → `Decimal`, required-field and category-shape checks. No file I/O, so it is testable with plain dicts. | Validation rules change |
| `modes/registry.py` | Maps CLI mode name → `ReportMode` class. Exposes a `@register("name")` decorator, a `get(name)` lookup that raises `UnknownReportModeError`, and `available()` for `--help`. | Registry mechanics change (rare) |
| `modes/by_category.py` | `CategorySummaryMode` — groups transactions by category, sums amounts, sorts descending. One report, one file. | This one report changes |
| `modes/monthly.py` | `MonthlyTotalsMode` — groups by `YYYY-MM`, sums, sorts chronologically. | This one report changes |
| `formatters/table.py` | `TableFormatter` — turns a `Report` into aligned plain-text lines. Computes column widths, right-aligns amounts, appends a total row. **Returns a string; does not print.** | Output appearance changes |
| `formatters/console.py` | `ConsoleWriter` — the single place that calls `print`/writes to a stream. Takes the stream as a constructor argument so tests pass a `StringIO`. | Output destination changes |

### How the layout satisfies SOLID

- **Single Responsibility (SRP)** — The table above is the proof: each row names
  one distinct reason to change. Loading never formats; formatting never reads
  files; report logic never touches I/O at all.
- **Open/Closed (OCP)** — The system is open to new report modes and new data
  sources, closed to modification. A new report is a new file plus a decorator;
  `engine.py`, `cli.py`, and `formatters/` are never edited. This is the
  principle the whole design is organized around.
- **Liskov Substitution (LSP)** — Any `ReportMode` is usable wherever the
  interface is expected because the contract is total: `process_transactions`
  always returns a `Report`, and returns an *empty* `Report` for empty input
  rather than raising or returning `None`. No subclass strengthens the
  preconditions.
- **Interface Segregation (ISP)** — Two narrow, single-method interfaces rather
  than one fat `DataProcessor`. A report mode is not forced to know about file
  paths; a loader is not forced to know about aggregation.
- **Dependency Inversion (DIP)** — `ReportEngine` depends on the `TransactionLoader`
  and `ReportMode` abstractions, never on `CsvTransactionLoader` or
  `CategorySummaryMode`. Concretes are selected at the outermost layer (`cli.py`)
  and injected inward, so tests can inject a list-backed fake loader with no
  filesystem involved.

---

## 5. Module Dependency Diagram and Data Flow

### Dependency graph

Arrows point from *depends on* to *depended upon*. Note that no arrow ever
enters `cli.py` or `main.py` — nothing depends on the outermost layer.

```
                       ┌──────────┐
                       │ main.py  │
                       └────┬─────┘
                            │
                       ┌────▼─────┐
              ┌────────┤  cli.py  ├─────────────┐
              │        └────┬─────┘             │
              │             │                   │
     ┌────────▼───────┐ ┌───▼──────┐   ┌────────▼──────────┐
     │ loaders/       │ │ engine.py│   │ modes/registry.py │
     │  csv_loader.py │ └───┬──────┘   └────────┬──────────┘
     └────────┬───────┘     │                   │
              │             │          ┌────────▼─────────┐
     ┌────────▼───────┐     │          │ modes/           │
     │ loaders/       │     │          │  by_category.py  │
     │  validation.py │     │          │  monthly.py      │
     └────────┬───────┘     │          └────────┬─────────┘
              │             │                   │
              └─────────────┼───────────────────┘
                            │
                  ┌─────────▼──────────┐
                  │   interfaces.py    │  ◄── the inversion point
                  │   models.py        │
                  │   errors.py        │
                  └────────────────────┘
                            ▲
                            │
                  ┌─────────┴──────────┐
                  │ formatters/        │
                  │  table.py          │
                  │  console.py        │
                  └────────────────────┘
```

`interfaces.py`, `models.py`, and `errors.py` are leaves — they import nothing
from the project. Everything else depends on them. That is what keeps the graph
acyclic.

### Runtime data flow

```
  $ expense-tracker data/expenses.csv --mode by-category

  argv
   │
   ▼
 cli.py ──────────────► registry.get("by-category") ──► CategorySummaryMode
   │                                                          │
   │  constructs CsvTransactionLoader()                       │
   │                                                          │
   ▼                                                          │
 ReportEngine(loader, mode).run(path)                         │
   │                                                          │
   ├─► loader.load(path) ──► csv.DictReader ──► validation ───┤
   │        │                                                 │
   │        └──► List[Transaction]  (typed, validated) ───────┤
   │                                                          │
   ├─► mode.process_transactions(transactions) ◄──────────────┘
   │        │
   │        └──► Report(title, rows, total)
   │
   ▼
 TableFormatter.format(report) ──► str
   │
   ▼
 ConsoleWriter.write(text) ──► stdout        exit 0

 Any ExpenseTrackerError raised anywhere above
   └──► caught in cli.py ──► stderr message ──► exit 1 / 2
```

Note the direction of the transformations: `path → List[Transaction] → Report →
str → stdout`. Each arrow is a different module, and each intermediate value is
an ordinary Python object that a test can construct directly.

---

## 6. File and Folder Structure

```
expense-tracker/
├── main.py                        # CLI entry point (thin; delegates to cli.py)
├── README.md
├── interfaces.py                  # ABCs: TransactionLoader, ReportMode
├── project_structure.txt          # this layout, annotated
├── architecture_plan.md           # this document
│
├── expense_tracker/               # application package
│   ├── __init__.py
│   ├── cli.py                     # argparse, wiring, top-level error handling
│   ├── engine.py                  # ReportEngine — orchestration only
│   ├── models.py                  # Transaction, ReportRow, Report
│   ├── errors.py                  # ExpenseTrackerError hierarchy
│   │
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── csv_loader.py          # CsvTransactionLoader (implements interface)
│   │   └── validation.py          # pure field parsing/validation helpers
│   │
│   ├── modes/
│   │   ├── __init__.py            # imports each mode module to populate registry
│   │   ├── registry.py            # @register decorator, get(), available()
│   │   ├── by_category.py         # CategorySummaryMode
│   │   └── monthly.py             # MonthlyTotalsMode
│   │
│   └── formatters/
│       ├── __init__.py
│       ├── table.py               # Report -> aligned text (returns str)
│       └── console.py             # writes text to an injected stream
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # shared fixtures: sample transactions, tmp CSVs
│   ├── fakes.py                   # InMemoryLoader, RecordingWriter test doubles
│   ├── test_csv_loader.py         # incl. missing file, bad rows, empty file
│   ├── test_validation.py         # date/Decimal coercion edge cases
│   ├── test_by_category.py        # aggregation correctness, empty input
│   ├── test_monthly.py
│   ├── test_engine.py             # orchestration with fakes — no filesystem
│   ├── test_registry.py           # registration, unknown-mode error
│   ├── test_table_formatter.py    # column alignment, totals row
│   └── test_cli.py                # argv parsing, exit codes, error messages
│
└── data/
    ├── expenses.csv               # sample input
    └── malformed.csv              # fixture for error-path tests
```

**Why this shape:** `loaders/`, `modes/`, and `formatters/` are the three
directories expected to gain files over time; each corresponds to one interface
or one output concern. The flat files at package root (`cli`, `engine`, `models`,
`errors`) are the fixed core. The test tree mirrors the source tree one-to-one,
so the test for any module is findable by name.

`interfaces.py` sits at the repository root rather than inside the package
because the exercise's validation suite looks for it there; in a production
layout it would live at `expense_tracker/interfaces.py`.

---

## 7. Extension Points

### 7.1 Adding a new report type — the primary extension point

Three steps, **zero edits to existing logic**:

1. Create `expense_tracker/modes/weekly.py`:

   ```python
   from typing import List
   from ..interfaces import ReportMode
   from ..models import Report, ReportRow, Transaction
   from .registry import register


   @register("weekly")
   class WeeklyTotalsMode(ReportMode):
       """Totals spend per ISO week."""

       name = "weekly"
       description = "Total spend per ISO week"

       def process_transactions(self, transactions: List[Transaction]) -> Report:
           ...
   ```

2. Add the import line to `modes/__init__.py` so the decorator runs.
3. Add `tests/test_weekly.py`.

The engine, CLI, formatters, loaders, and every other report mode are untouched.
`--mode weekly` and the `--help` listing both work immediately, because the CLI
reads its choices from `registry.available()`.

> **Design note on the registry's one seam.** Step 2 is a one-line edit to an
> existing file, which is a small compromise against a literal reading of OCP.
> It is deliberate: the alternative — `pkgutil`-based auto-discovery that scans
> the `modes/` package — removes the edit but introduces implicit magic, slower
> startup, and failure modes that are hard to debug. An explicit import list is
> the better trade for a tool of this size. If the mode count ever grows past
> roughly a dozen, revisit auto-discovery.

### 7.2 Adding a new data source

Implement `TransactionLoader` in a new `loaders/json_loader.py`, then select it
in `cli.py` based on the file extension. `ReportEngine` and every report mode
are unaffected, because they only ever see `List[Transaction]`. This is
Dependency Inversion paying for itself.

### 7.3 Adding a new output format

Implement a formatter with the same `format(report) -> str` shape (e.g.
`formatters/csv_out.py`, `formatters/json_out.py`) and add a `--format` flag.
Because `TableFormatter` returns a string rather than printing, an alternative
formatter is a drop-in substitute and `ConsoleWriter` stays unchanged.

### 7.4 Adding filters

A future `--category` or `--since` flag becomes a transformation applied between
loading and processing, inside `ReportEngine`. It composes with every existing
report mode automatically, because filtering operates on `List[Transaction]` —
the shared currency of the pipeline.

---

## 8. Testing Strategy

The architecture is arranged so that almost every test is a fast, pure unit test.

| Layer | How it is tested | Why it's easy |
|---|---|---|
| `validation.py` | Plain dicts in, values or exceptions out | No I/O at all |
| `loaders/csv_loader.py` | `tmp_path` fixtures with good, malformed, empty, and missing files | I/O is confined to this one module |
| `modes/*.py` | Hand-built `List[Transaction]` in, `Report` asserted out | Report logic never touches the filesystem |
| `engine.py` | Injected `InMemoryLoader` fake + a stub mode | DIP means no real collaborators are needed |
| `formatters/table.py` | `Report` in, exact string compared | Formatting returns a value instead of printing |
| `formatters/console.py` | `StringIO` injected as the stream | The stream is a constructor argument |
| `cli.py` | `run([...])` called with an argv list; exit code and captured stderr asserted | `main.py` owns `sys.exit`, so `cli.run` is callable |

**Error-path cases to cover explicitly:** file not found; unreadable file
(permissions); empty file; header-only file; missing required column;
unparseable date; unparseable amount; negative amount; unknown `--mode` value;
and a report over zero matching transactions.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Registry not populated → "unknown mode" for a mode that exists | Explicit imports in `modes/__init__.py`; a registry test asserts every shipped mode resolves |
| Float rounding produces `19.999999` in money totals | Use `decimal.Decimal` for all amounts, from parse through display; never `float` |
| Path traversal / reading unintended files | Resolve the input path and validate it is an existing regular file before opening; report the path back in errors without echoing file contents |
| Very large CSV exhausts memory | Loader returns a list today; the `TransactionLoader` contract permits returning any iterable, so a streaming loader can be swapped in without changing the interface |
| Unicode / BOM in CSV headers | Open with `encoding="utf-8-sig"` and `newline=""`; a test fixture covers a BOM-prefixed file |
| Modules drift past the 200-line cap | The one unbounded axis (report count) maps to new files; a lint check in CI can enforce the cap |

---

## 10. Summary of the Decision

**We will use a four-layer architecture (presentation → orchestration → domain →
data access) with the Strategy pattern for report modes, a decorator-based
registry for mode discovery, and constructor injection throughout.**

This was chosen over a single-module script (Alternative A) and over layered
modules with conditional dispatch (Alternative B) because it is the only one of
the three in which the system's expected axis of growth — new report types —
requires adding code rather than modifying it. The trade-off accepted is a
modest increase in file count and one level of indirection through the registry,
in exchange for Open/Closed compliance at the point where it matters, modules
that stay under the 200-line cap by construction, and a test suite that needs
almost no filesystem access.
