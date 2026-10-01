"""CSV loading and validation for expense tracker transactions.

Defines the :class:`TransactionLoader` interface and its CSV implementation,
:class:`CSVTransactionLoader`. The loader is the one boundary at which
untrusted file data enters the application, so every row is validated here.

Expected header: ``date,amount,category,description``. Every field must be
non-empty, ``amount`` must be finite and positive, and whitespace is stripped
from all fields. Loading fails fast: the first invalid row raises, reporting
its line number as it appears in the file.

Usage:
    >>> loader = CSVTransactionLoader()
    >>> loader.load("expenses.csv")  # doctest: +SKIP
    [{'date': '2024-01-15', 'amount': 45.5, 'category': 'Food',
      'description': 'Grocery shopping'}]
"""

import csv
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class TransactionLoader(ABC):
    """Interface for loading transaction records from a data source.

    Implementations read one concrete source (CSV, JSON, database) and return a
    uniform list of transaction dicts, keeping report code independent of
    storage format.
    """

    @abstractmethod
    def load(self, filepath: str) -> List[Dict[str, Any]]:
        """Load transactions from ``filepath``.

        Args:
            filepath: Path to the source file.

        Returns:
            List of dicts with keys: date, amount, category, description.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format or any record is invalid.
        """


class CSVTransactionLoader(TransactionLoader):
    """Loads expense transactions from a CSV file, validating every row.

    Returns one dict per data row with ``amount`` coerced to ``float`` and text
    fields stripped. Raises on the first malformed row rather than skipping it,
    so a partly bad file never yields a silently incomplete report.
    """

    REQUIRED_COLUMNS: tuple = ("date", "amount", "category", "description")

    def load(self, filepath: str) -> List[Dict[str, Any]]:
        """Load and validate all transactions from a CSV file.

        Args:
            filepath: Path to the CSV file to read.

        Returns:
            Validated transaction dicts in file order; empty if header-only.

        Raises:
            FileNotFoundError: If ``filepath`` does not exist.
            ValueError: If the path is not a regular file, the file is empty,
                a required column is absent, or any row fails validation.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"No such transaction file: {filepath!r}")
        if not path.is_file():
            raise ValueError(f"Not a regular file: {filepath!r}")

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(
                    f"{filepath!r} is empty; a header row naming "
                    f"{', '.join(self.REQUIRED_COLUMNS)} is required"
                )

            # Reading .fieldnames consumed the header; reassigning the stripped
            # names lets padded headers ("date, amount") still key rows cleanly.
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            missing = [c for c in self.REQUIRED_COLUMNS if c not in reader.fieldnames]
            if missing:
                raise ValueError(
                    f"{filepath!r} is missing required column(s): {', '.join(missing)}"
                )

            try:
                # start=2: the header occupies row 1 of the file.
                return [
                    self._validate_row(row, row_number)
                    for row_number, row in enumerate(reader, start=2)
                ]
            except csv.Error as exc:
                raise ValueError(f"Malformed CSV in {filepath!r}: {exc}") from exc

    def _validate_row(self, row: Dict[str, Any], row_number: int) -> Dict[str, Any]:
        """Validate one CSV row and return it as a clean transaction dict.

        Args:
            row: Raw row mapping from :class:`csv.DictReader`.
            row_number: 1-based file line number, used in error messages.

        Returns:
            Dict with the four required keys, stripped, ``amount`` as a float.

        Raises:
            ValueError: If a required field is absent or empty, or if ``amount``
                is not numeric, not finite, or not greater than zero.
        """
        transaction: Dict[str, Any] = {}
        for column in self.REQUIRED_COLUMNS:
            value = row.get(column)
            if value is None:
                raise ValueError(
                    f"Row {row_number}: no value for column {column!r} "
                    f"(row has fewer fields than the header)"
                )
            value = value.strip()
            if not value:
                raise ValueError(f"Row {row_number}: {column!r} must not be empty")
            transaction[column] = value

        raw_amount = transaction["amount"]
        try:
            amount = float(raw_amount)
        except ValueError as exc:
            raise ValueError(
                f"Row {row_number}: amount {raw_amount!r} is not a number"
            ) from exc
        if not math.isfinite(amount):
            raise ValueError(
                f"Row {row_number}: amount {raw_amount!r} is not a finite number"
            )
        if amount <= 0:
            raise ValueError(f"Row {row_number}: amount must be positive, got {amount}")

        transaction["amount"] = amount
        return transaction
