"""Report strategies for aggregating expense transactions.

This module applies the **Strategy pattern**: :class:`ReportMode` declares one
interface for turning a list of transactions into a report, and each concrete
subclass supplies a different aggregation rule. Callers hold a ``ReportMode``
and never branch on report type, so adding a report means adding a class here
rather than editing existing code (Open/Closed).

Every strategy returns the same three-key shape, which keeps the display layer
independent of which report ran::

    {"mode": "summary", "data": {"Food": 101.49}, "total": 101.49}

Transactions are dicts as produced by ``transaction_loader``, with keys
``date``, ``amount``, ``category`` and ``description``.

Usage:
    >>> transactions = [
    ...     {"date": "2024-01-15", "amount": 45.50, "category": "Food",
    ...      "description": "Grocery"},
    ...     {"date": "2024-02-10", "amount": 75.00, "category": "Fun",
    ...      "description": "Concert"},
    ... ]
    >>> for strategy in (SummaryByCategory(), MonthlyTotalReport()):
    ...     report = strategy.process_transactions(transactions)
    ...     print(strategy.get_mode_name(), report["data"], report["total"])
    summary {'Food': 45.5, 'Fun': 75.0} 120.5
    monthly {'2024-01': 45.5, '2024-02': 75.0} 120.5
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class ReportMode(ABC):
    """Interface every report strategy implements.

    Concrete strategies are interchangeable: a caller can swap one for another
    without changing anything but the object it was handed.
    """

    @abstractmethod
    def process_transactions(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Aggregate transactions into report data.

        Args:
            transactions: Transaction dicts with date, amount, category,
                description keys.

        Returns:
            Dict with ``mode`` (this strategy's name), ``data`` (grouping key
            to summed amount) and ``total`` (sum across all groups).
        """

    @abstractmethod
    def get_mode_name(self) -> str:
        """Return this strategy's short name, as used in the ``mode`` key."""


def _sum_amounts_by(
    transactions: List[Dict[str, Any]],
    group_key: Callable[[Dict[str, Any]], Optional[str]],
) -> Dict[str, float]:
    """Group transactions by a derived key and sum their amounts.

    Shared by every strategy so the grouping loop exists once; strategies
    differ only in the ``group_key`` they pass.

    Args:
        transactions: Transaction dicts to aggregate.
        group_key: Returns the grouping key for one transaction, or ``None``
            to exclude that transaction from the report.

    Returns:
        Mapping of grouping key to summed amount, rounded to two decimals.
        Empty dict when no transaction yields a key.
    """
    sums: Dict[str, float] = defaultdict(float)
    for transaction in transactions:
        key = group_key(transaction)
        if key is not None:
            sums[key] += float(transaction.get("amount", 0.0))
    return {key: round(amount, 2) for key, amount in sums.items()}


class SummaryByCategory(ReportMode):
    """Totals spending per category, answering "where does my money go?".

    Groups every transaction by its ``category`` field and sums the amounts,
    so repeated categories collapse into one entry. Transactions with a blank
    or missing category are counted under ``"Uncategorized"`` rather than
    dropped, so the total always reflects every input row.

    Example:
        >>> rows = [{"date": "2024-01-15", "amount": 45.50,
        ...          "category": "Food", "description": "Grocery"}]
        >>> SummaryByCategory().process_transactions(rows)
        {'mode': 'summary', 'data': {'Food': 45.5}, 'total': 45.5}
    """

    MODE_NAME = "summary"

    def process_transactions(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Sum amounts per category. See :meth:`ReportMode.process_transactions`."""
        by_category = _sum_amounts_by(transactions, self._category_of)
        return {
            "mode": self.MODE_NAME,
            "data": by_category,
            "total": round(sum(by_category.values(), 0.0), 2),
        }

    def get_mode_name(self) -> str:
        """Return ``"summary"``."""
        return self.MODE_NAME

    @staticmethod
    def _category_of(transaction: Dict[str, Any]) -> str:
        """Return the transaction's category, or ``"Uncategorized"`` if blank."""
        category = str(transaction.get("category", "")).strip()
        return category or "Uncategorized"


class MonthlyTotalReport(ReportMode):
    """Totals spending per calendar month, showing trends over time.

    Groups transactions by the ``YYYY-MM`` prefix of their ``date`` field and
    sums the amounts. A transaction whose date is missing or not a valid
    ``YYYY-MM-DD`` string is skipped rather than raising, so one bad row does
    not cost the whole report; skipped rows are absent from both ``data`` and
    ``total``.

    Example:
        >>> rows = [{"date": "2024-02-10", "amount": 75.00,
        ...          "category": "Fun", "description": "Concert"}]
        >>> MonthlyTotalReport().process_transactions(rows)
        {'mode': 'monthly', 'data': {'2024-02': 75.0}, 'total': 75.0}
    """

    MODE_NAME = "monthly"
    MONTH_LENGTH = 7

    def process_transactions(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Sum amounts per month. See :meth:`ReportMode.process_transactions`."""
        by_month = _sum_amounts_by(transactions, self._month_of)
        return {
            "mode": self.MODE_NAME,
            "data": dict(sorted(by_month.items())),
            "total": round(sum(by_month.values(), 0.0), 2),
        }

    def get_mode_name(self) -> str:
        """Return ``"monthly"``."""
        return self.MODE_NAME

    @classmethod
    def _month_of(cls, transaction: Dict[str, Any]) -> Optional[str]:
        """Return the ``YYYY-MM`` prefix of the date, or ``None`` if unusable."""
        raw_date = transaction.get("date")
        if not isinstance(raw_date, str):
            return None
        month = raw_date.strip()[: cls.MONTH_LENGTH]
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            return None
        return month
