"""
CLI Interface Module - Version 2

Displays reports in terminal with formatting and color.

Refactored from version 1. Structure only - behavior, public API, and
output format are byte-for-byte identical to v1.

Layout and presentation literals are defined as class constants on
``CLIInterface`` (see LINE_WIDTH, LABEL_WIDTH, AMOUNT_WIDTH, BORDER_CHAR,
DIVIDER_CHAR, ERROR_CHAR and friends) rather than being repeated inline.
"""

from typing import Any, Mapping, TypedDict


class ReportData(TypedDict, total=False):
    """
    Shape of the dictionary accepted by :meth:`CLIInterface.display_report`.

    All keys are optional: v1 reads them with ``.get()`` and falls back to
    defaults, so a partial dictionary renders an empty report rather than
    raising. ``total=False`` documents that contract.
    """

    mode: str
    data: Mapping[str, float]
    total: float


class CLIInterface:
    """
    Terminal interface for displaying expense reports.

    Presentation constants
    ----------------------
    Layout:
        LINE_WIDTH      - width of every horizontal rule
        LABEL_WIDTH     - left-aligned width of a row label
        AMOUNT_WIDTH    - right-aligned width of a row amount
        AMOUNT_DECIMALS - decimal places shown for an amount
        INDENT          - leading indent applied to every text line

    Characters:
        BORDER_CHAR     - report top/bottom rule
        DIVIDER_CHAR    - rule between rows and the total
        ERROR_CHAR      - error banner rule
        CURRENCY_SYMBOL - prefix on every amount

    Text:
        TOTAL_LABEL, UNKNOWN_MODE, REPORT_TITLES, and the ERROR_HEADING_*
        headings.

    Classification:
        FILE_ERROR_KEYWORDS, DATA_ERROR_KEYWORDS - substrings used to pick
        an error heading.
    """

    # Layout
    LINE_WIDTH: int = 50
    LABEL_WIDTH: int = 20
    AMOUNT_WIDTH: int = 10
    AMOUNT_DECIMALS: int = 2
    INDENT: str = "  "

    # Characters
    BORDER_CHAR: str = "="
    DIVIDER_CHAR: str = "-"
    ERROR_CHAR: str = "!"
    CURRENCY_SYMBOL: str = "$"

    # Text
    TOTAL_LABEL: str = "TOTAL"
    UNKNOWN_MODE: str = "unknown"
    REPORT_TITLES: Mapping[str, str] = {
        "summary": "EXPENSE SUMMARY BY CATEGORY",
        "monthly": "MONTHLY EXPENSE TOTALS",
    }

    ERROR_HEADING_FILE: str = "ERROR: File Not Found"
    ERROR_HEADING_DATA: str = "ERROR: Invalid Data"
    ERROR_HEADING_GENERIC: str = "ERROR"

    # Classification keywords, matched against the lowercased message.
    FILE_ERROR_KEYWORDS: tuple[str, ...] = ("file", "not found")
    DATA_ERROR_KEYWORDS: tuple[str, ...] = ("invalid", "value")

    def display_report(self, report_data: ReportData) -> None:
        """
        Display formatted report to terminal.

        Args:
            report_data: Report payload with 'mode', 'data' and 'total' keys.
                Missing keys fall back to defaults, matching v1.
        """
        mode = report_data.get("mode", self.UNKNOWN_MODE)
        title = self.REPORT_TITLES.get(mode)

        if title is None:
            print(f"\nError: Unknown report mode '{mode}'\n")
            return

        print(self._format_header(title))

        data = report_data.get("data", {})
        for label, amount in sorted(data.items()):
            print(self._format_row(label, amount))

        print(self._format_footer(report_data.get("total", 0.0)))

    def display_error(self, error: Any) -> None:
        """
        Display error message to terminal.

        Args:
            error: Exception or any object; rendered via ``str(error)``.
        """
        error_str = str(error)
        heading = self._error_heading(error_str)
        print(self._format_error_message(error_str, heading))

    def _format_header(self, title: str) -> str:
        """
        Build the report header: leading blank line, rule, title, rule.

        Args:
            title: Heading text shown between the two rules.

        Returns:
            Header block, without its trailing newline (``print`` adds it).
        """
        border = self.BORDER_CHAR * self.LINE_WIDTH
        return f"\n{border}\n{self.INDENT}{title}\n{border}"

    def _format_row(self, label: str, amount: float) -> str:
        """
        Build one data row: indented label, then a right-aligned amount.

        Neither field is truncated, so an over-long label or amount widens
        the row past LINE_WIDTH - same as v1.

        Args:
            label: Category or month name.
            amount: Value shown after the currency symbol.

        Returns:
            Single formatted row.
        """
        return (
            f"{self.INDENT}{label:{self.LABEL_WIDTH}s} "
            f"{self.CURRENCY_SYMBOL}"
            f"{amount:>{self.AMOUNT_WIDTH}.{self.AMOUNT_DECIMALS}f}"
        )

    def _format_footer(self, total: float) -> str:
        """
        Build the report footer: divider, total row, rule, trailing blank line.

        Args:
            total: Report total.

        Returns:
            Footer block, without its trailing newline (``print`` adds it).
        """
        divider = self.DIVIDER_CHAR * self.LINE_WIDTH
        border = self.BORDER_CHAR * self.LINE_WIDTH
        total_row = self._format_row(self.TOTAL_LABEL, total)
        return f"{divider}\n{total_row}\n{border}\n"

    def _format_error_message(
        self,
        msg: str,
        heading: str = ERROR_HEADING_GENERIC,
    ) -> str:
        """
        Wrap an error message in the banner shared by every error kind.

        Args:
            msg: Error detail text.
            heading: Banner heading; defaults to the generic ERROR heading.

        Returns:
            Banner block, without its trailing newline (``print`` adds it).
        """
        border = self.ERROR_CHAR * self.LINE_WIDTH
        return (
            f"\n{border}\n"
            f"{self.INDENT}{heading}\n"
            f"{self.INDENT}{msg}\n"
            f"{border}\n"
        )

    def _error_heading(self, error_str: str) -> str:
        """
        Pick the banner heading for an error message.

        Classification is by substring, checking file keywords before data
        keywords. This reproduces v1 exactly, including its quirks: a
        ValueError reading "Invalid file path" is headed "File Not Found"
        because 'file' is tested first. Preserved deliberately - the output
        format is fixed for this refactor; see the code review for a
        type-based replacement.

        Args:
            error_str: Already-stringified error message.

        Returns:
            One of the ERROR_HEADING_* constants.
        """
        lowered = error_str.lower()

        if any(keyword in lowered for keyword in self.FILE_ERROR_KEYWORDS):
            return self.ERROR_HEADING_FILE
        if any(keyword in lowered for keyword in self.DATA_ERROR_KEYWORDS):
            return self.ERROR_HEADING_DATA
        return self.ERROR_HEADING_GENERIC
