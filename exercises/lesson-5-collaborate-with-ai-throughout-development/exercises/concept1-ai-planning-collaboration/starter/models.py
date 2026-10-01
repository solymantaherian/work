"""Immutable domain value types shared by every layer of the expense tracker.

These types are the *currency* of the pipeline: a loader produces
``Transaction`` objects, a report mode consumes them and produces a ``Report``,
and a formatter consumes the ``Report``. Because every boundary speaks in these
types, each layer can be tested by constructing them directly -- no filesystem,
no stdout, no mocks.

All types are ``NamedTuple`` subclasses, which gives us for free:

* immutability (a report mode cannot corrupt the caller's data),
* structural equality (``assert result == expected`` in tests just works),
* a readable ``repr`` for test failure output,
* zero dependencies beyond the standard library.

Monetary amounts are ``decimal.Decimal``, never ``float``. Binary floating
point cannot represent 0.1 exactly, so summing float amounts produces totals
like ``19.999999999999996``. ``Decimal`` is exact for base-10 fractions, which
is what money is.

In the shipped package this module lives at ``src/expense_tracker/models.py``.
It sits at the repository root here so the planning artifacts remain a
self-contained, importable set.
"""
from datetime import date
from decimal import Decimal
from typing import Sequence, Tuple


class Transaction(NamedTupleBase := __import__("typing").NamedTuple):
    """A single validated expense record loaded from a data source.

    A ``Transaction`` is only ever created by a :class:`TransactionLoader`
    implementation, and only after validation has succeeded. Downstream code
    may therefore assume every field is present and well-typed -- report modes
    should not re-check for ``None`` or attempt string parsing.

    Attributes:
        date: The calendar date the expense occurred, as a ``datetime.date``.
            Already parsed; never a string.
        amount: The expense amount as an exact ``Decimal``. Positive for
            spending. Never a ``float``.
        category: Non-empty category label, already stripped of surrounding
            whitespace (e.g. ``"Groceries"``).
        description: Free-text description. May be an empty string -- an
            absent description is not a validation failure -- but is never
            ``None``.
    """

    date: date
    amount: Decimal
    category: str
    description: str


class ReportRow(NamedTupleBase):
    """One aggregated line in a report.

    A row is the output of grouping, not a raw transaction. ``label`` is
    whatever the report mode grouped by -- a category name, a ``"2026-09"``
    month key, an ISO week -- and the formatter treats it as an opaque string.

    Attributes:
        label: The group key, rendered for display.
        amount: Sum of the amounts in this group, as an exact ``Decimal``.
        count: How many transactions were folded into this row. Defaults to 1
            so single-transaction rows need not pass it explicitly.
    """

    label: str
    amount: Decimal
    count: int = 1


class Report(NamedTupleBase):
    """The complete result of running one report mode over a transaction set.

    This is the only type a :class:`ReportMode` may return. Keeping the return
    shape fixed is what allows the formatting layer to stay generic: a new
    report mode never requires a new formatter.

    Attributes:
        title: Human-readable heading, supplied by the report mode
            (e.g. ``"Spending by Category"``).
        rows: The aggregated rows, in the order the mode chose. Ordering is
            part of each mode's own contract -- the formatter never re-sorts.
        total: Sum of ``row.amount`` across all rows. Stored rather than
            recomputed so a mode can define a total that is not a plain sum
            (an average, a net figure) without fighting the type.
    """

    title: str
    rows: Tuple[ReportRow, ...]
    total: Decimal

    @classmethod
    def empty(cls, title: str) -> "Report":
        """Build the canonical empty report.

        Report modes must return this (rather than ``None`` or raising) when
        given no transactions, or when no transaction matches their criteria.
        That is what makes every mode substitutable for every other -- see the
        Liskov note in ``interfaces.py``.

        Args:
            title: The heading the report would have carried had it had rows.

        Returns:
            A ``Report`` with no rows and a zero total.
        """
        return cls(title=title, rows=(), total=Decimal("0"))

    @property
    def is_empty(self) -> bool:
        """Whether the report produced no rows.

        Formatters use this to print "No transactions matched." instead of an
        empty table with a lonely 0.00 total.
        """
        return len(self.rows) == 0

    @property
    def transaction_count(self) -> int:
        """Total number of transactions represented across all rows."""
        return sum(row.count for row in self.rows)


def sum_amounts(rows: Sequence[ReportRow]) -> Decimal:
    """Sum the amounts of a row sequence, returning an exact ``Decimal``.

    A convenience for report modes building a ``Report``: ``sum()`` on an empty
    sequence returns the integer ``0``, which would make ``Report.total``
    inconsistently typed. This always returns a ``Decimal``.

    Args:
        rows: The rows to total. May be empty.

    Returns:
        The exact sum, or ``Decimal("0")`` for an empty sequence.
    """
    total = Decimal("0")
    for row in rows:
        total += row.amount
    return total
