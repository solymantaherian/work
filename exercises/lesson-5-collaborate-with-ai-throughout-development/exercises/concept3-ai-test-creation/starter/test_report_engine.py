"""
Comprehensive pytest test suite for the ReportEngine class.

ReportEngine is a thin orchestrator (Facade): it delegates loading to a
TransactionLoader and processing to a ReportMode strategy. Every test here
therefore mocks BOTH collaborators so that failures point at ReportEngine
itself rather than at a loader or strategy implementation.

Test organization:
    TestReportEngineBasics        - construction and basic contract
    TestReportGenerationHappyPath - successful generation and data flow
    TestReportGenerationErrors    - exception propagation and failure handling
    TestEdgeCases                 - boundary and unusual-input scenarios

Run:
    pytest test_report_engine.py -v
"""

import pytest
from unittest.mock import Mock, call

from report_engine import ReportEngine


# ---------------------------------------------------------------------------
# Fixtures
#
# All fixtures are function-scoped (pytest's default), so every test receives
# a freshly built object. No state is shared between tests.
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_transactions():
    """Provide a small, fixed list of transaction records.

    Deterministic by design: the same values every run, so assertions on
    totals and ordering are stable.
    """
    return [
        {'date': '2024-01-15', 'amount': 45.50, 'category': 'Food',
         'description': 'Lunch at cafe'},
        {'date': '2024-01-16', 'amount': 120.00, 'category': 'Transport',
         'description': 'Monthly rail pass'},
        {'date': '2024-02-03', 'amount': 62.25, 'category': 'Food',
         'description': 'Groceries'},
    ]


@pytest.fixture
def single_transaction():
    """Provide a one-element transaction list for boundary testing."""
    return [
        {'date': '2024-01-15', 'amount': 45.50, 'category': 'Food',
         'description': 'Lunch at cafe'},
    ]


@pytest.fixture
def large_transaction_set():
    """Provide 1500 transactions built deterministically (no randomness).

    Used to confirm ReportEngine does not degrade, truncate, or copy large
    payloads as they pass from loader to mode.
    """
    categories = ['Food', 'Transport', 'Utilities', 'Entertainment']
    return [
        {
            'date': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            'amount': round(10.00 + (i % 100), 2),
            'category': categories[i % len(categories)],
            'description': f'Transaction number {i}',
        }
        for i in range(1500)
    ]


@pytest.fixture
def transactions_with_special_chars():
    """Provide transactions containing delimiters, quotes, and unicode.

    These are the values most likely to be mangled by naive string handling
    somewhere in the pipeline.
    """
    return [
        {'date': '2024-01-15', 'amount': 45.50, 'category': 'Food & Drink',
         'description': 'Cafe "Le Marais", table 3'},
        {'date': '2024-01-16', 'amount': 120.00, 'category': 'Transport',
         'description': 'Taxi — 50% surcharge; late night'},
        {'date': '2024-01-17', 'amount': 15.75, 'category': 'Café',
         'description': 'Kaffee mit Brötchen \U0001F950'},
    ]


@pytest.fixture
def mock_loader():
    """Provide a mock TransactionLoader returning an empty list by default.

    Individual tests override `load.return_value` or `load.side_effect`.
    """
    loader = Mock(name='TransactionLoader')
    loader.load.return_value = []
    return loader


@pytest.fixture
def mock_mode():
    """Provide a mock ReportMode returning a representative report dict."""
    mode = Mock(name='ReportMode')
    mode.process_transactions.return_value = {
        'mode': 'summary',
        'data': {'Food': 107.75, 'Transport': 120.00},
        'total': 227.75,
    }
    return mode


@pytest.fixture
def report_engine(mock_loader):
    """Provide a ReportEngine wired to the mock loader."""
    return ReportEngine(mock_loader)


# ---------------------------------------------------------------------------
# 1. Basic functionality
# ---------------------------------------------------------------------------


class TestReportEngineBasics:
    """Construction and the basic shape of the generate_report contract."""

    def test_initialization_stores_loader(self, mock_loader):
        """Should keep the injected loader as the `loader` attribute."""
        # Arrange / Act
        engine = ReportEngine(mock_loader)

        # Assert
        assert engine.loader is mock_loader, \
            "ReportEngine should store the exact loader instance it was given"

    def test_initialization_does_not_call_loader(self, mock_loader):
        """Should not perform any loading work during construction."""
        # Arrange / Act
        ReportEngine(mock_loader)

        # Assert
        mock_loader.load.assert_not_called()

    def test_generate_report_returns_dictionary(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should return a dict-shaped report for valid input."""
        # Arrange
        mock_loader.load.return_value = sample_transactions

        # Act
        result = report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        assert isinstance(result, dict), \
            f"Expected a dict report, got {type(result).__name__}"

    def test_generate_report_returns_expected_keys(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should return the report structure produced by the mode."""
        # Arrange
        mock_loader.load.return_value = sample_transactions

        # Act
        result = report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        assert set(result) == {'mode', 'data', 'total'}, \
            f"Report keys should come straight from the mode, got {sorted(result)}"

    def test_generate_report_with_valid_data_succeeds(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should produce the mode's report values for valid input."""
        # Arrange
        mock_loader.load.return_value = sample_transactions

        # Act
        result = report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        assert result['mode'] == 'summary'
        assert result['total'] == 227.75


# ---------------------------------------------------------------------------
# 2. Happy path scenarios
# ---------------------------------------------------------------------------


class TestReportGenerationHappyPath:
    """Successful generation, and the loader -> mode -> result data flow."""

    def test_generates_report_from_multiple_transactions(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should hand every loaded transaction to the mode unchanged."""
        # Arrange
        mock_loader.load.return_value = sample_transactions

        # Act
        report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        passed = mock_mode.process_transactions.call_args.args[0]
        assert passed == sample_transactions, \
            "All three transactions should reach the mode unmodified"

    def test_loader_called_once_with_given_filepath(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should read the requested file exactly once per report."""
        # Arrange / Act
        report_engine.generate_report('data/q1-expenses.csv', mock_mode)

        # Assert
        mock_loader.load.assert_called_once_with('data/q1-expenses.csv')

    def test_mode_receives_loader_output_verbatim(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should pass the loader's exact list object to the mode.

        Identity (`is`) matters here: ReportEngine must not copy, filter, or
        re-wrap the data on the way through.
        """
        # Arrange
        mock_loader.load.return_value = sample_transactions

        # Act
        report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        mock_mode.process_transactions.assert_called_once_with(sample_transactions)
        assert mock_mode.process_transactions.call_args.args[0] is sample_transactions

    def test_returns_mode_output_verbatim(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should return the mode's result object without post-processing."""
        # Arrange
        mock_loader.load.return_value = sample_transactions
        expected = {'mode': 'custom', 'data': {}, 'total': 0.0}
        mock_mode.process_transactions.return_value = expected

        # Act
        result = report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        assert result is expected, \
            "ReportEngine should return the mode's object, not a rebuilt copy"

    @pytest.mark.parametrize("mode_name,expected_report", [
        ('summary', {'mode': 'summary', 'data': {'Food': 107.75}, 'total': 107.75}),
        ('monthly', {'mode': 'monthly', 'data': {'2024-01': 165.50}, 'total': 165.50}),
        ('top', {'mode': 'top', 'data': {'Transport': 120.00}, 'total': 120.00}),
    ], ids=['summary', 'monthly', 'top'])
    def test_works_with_different_report_modes(
        self, report_engine, mock_loader, sample_transactions,
        mode_name, expected_report
    ):
        """Should work with any ReportMode strategy it is handed.

        ReportEngine is mode-agnostic, so swapping the strategy must change
        the output without changing the orchestration.
        """
        # Arrange
        mock_loader.load.return_value = sample_transactions
        mode = Mock(name=f'{mode_name}Mode')
        mode.process_transactions.return_value = expected_report

        # Act
        result = report_engine.generate_report('expenses.csv', mode)

        # Assert
        assert result == expected_report
        mode.process_transactions.assert_called_once_with(sample_transactions)

    def test_loads_before_processing(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should load transactions before invoking the mode.

        A shared parent mock records call order across both collaborators.
        """
        # Arrange
        mock_loader.load.return_value = sample_transactions
        recorder = Mock()
        recorder.attach_mock(mock_loader, 'loader')
        recorder.attach_mock(mock_mode, 'mode')

        # Act
        report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        assert recorder.mock_calls == [
            call.loader.load('expenses.csv'),
            call.mode.process_transactions(sample_transactions),
        ]

    def test_generates_multiple_reports_from_one_engine(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should support repeated calls without carrying state between them."""
        # Arrange
        mock_loader.load.return_value = sample_transactions

        # Act
        first = report_engine.generate_report('january.csv', mock_mode)
        second = report_engine.generate_report('february.csv', mock_mode)

        # Assert
        assert first == second
        assert mock_loader.load.call_args_list == [
            call('january.csv'), call('february.csv')
        ]


# ---------------------------------------------------------------------------
# 3. Error handling
# ---------------------------------------------------------------------------


class TestReportGenerationErrors:
    """Failure modes: ReportEngine propagates rather than swallowing errors."""

    def test_file_not_found_error_propagates_from_loader(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should let FileNotFoundError from the loader reach the caller."""
        # Arrange
        mock_loader.load.side_effect = FileNotFoundError(
            "No such file: 'missing.csv'"
        )

        # Act / Assert
        with pytest.raises(FileNotFoundError, match=r"No such file: 'missing\.csv'"):
            report_engine.generate_report('missing.csv', mock_mode)

    def test_value_error_propagates_for_invalid_csv(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should let ValueError from malformed CSV reach the caller."""
        # Arrange
        mock_loader.load.side_effect = ValueError(
            "Invalid CSV: malformed row at line 7"
        )

        # Act / Assert
        with pytest.raises(ValueError, match=r"malformed row at line 7"):
            report_engine.generate_report('corrupt.csv', mock_mode)

    def test_value_error_from_mode_propagates(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should let a ValueError raised during processing reach the caller."""
        # Arrange
        mock_loader.load.return_value = sample_transactions
        mock_mode.process_transactions.side_effect = ValueError(
            "Unsupported category: 'Unknown'"
        )

        # Act / Assert
        with pytest.raises(ValueError, match=r"Unsupported category"):
            report_engine.generate_report('expenses.csv', mock_mode)

    def test_permission_error_propagates_from_loader(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should not convert or mask OS-level loader failures."""
        # Arrange
        mock_loader.load.side_effect = PermissionError(
            "Permission denied: 'locked.csv'"
        )

        # Act / Assert
        with pytest.raises(PermissionError, match=r"Permission denied"):
            report_engine.generate_report('locked.csv', mock_mode)

    def test_mode_not_invoked_when_loader_fails(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should skip processing entirely when loading fails.

        Guards against a future refactor that processes partial data.
        """
        # Arrange
        mock_loader.load.side_effect = FileNotFoundError("missing.csv")

        # Act
        with pytest.raises(FileNotFoundError):
            report_engine.generate_report('missing.csv', mock_mode)

        # Assert
        mock_mode.process_transactions.assert_not_called()

    def test_empty_transaction_list_is_passed_to_mode(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should treat an empty file as valid input, not an error.

        Deciding what an empty report looks like belongs to the mode, so the
        engine must still delegate.
        """
        # Arrange
        mock_loader.load.return_value = []
        mock_mode.process_transactions.return_value = {
            'mode': 'summary', 'data': {}, 'total': 0.0
        }

        # Act
        result = report_engine.generate_report('empty.csv', mock_mode)

        # Assert
        mock_mode.process_transactions.assert_called_once_with([])
        assert result['total'] == 0.0

    def test_unexpected_loader_exception_propagates(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should not catch broad exceptions it cannot meaningfully handle."""
        # Arrange
        mock_loader.load.side_effect = RuntimeError("Database connection lost")

        # Act / Assert
        with pytest.raises(RuntimeError, match=r"Database connection lost"):
            report_engine.generate_report('expenses.csv', mock_mode)


# ---------------------------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary sizes and unusual-but-legal data."""

    def test_single_transaction_report(
        self, report_engine, mock_loader, mock_mode, single_transaction
    ):
        """Should handle a one-transaction file like any other."""
        # Arrange
        mock_loader.load.return_value = single_transaction
        mock_mode.process_transactions.return_value = {
            'mode': 'summary', 'data': {'Food': 45.50}, 'total': 45.50
        }

        # Act
        result = report_engine.generate_report('one.csv', mock_mode)

        # Assert
        mock_mode.process_transactions.assert_called_once_with(single_transaction)
        assert result['total'] == 45.50

    def test_very_large_transaction_list(
        self, report_engine, mock_loader, mock_mode, large_transaction_set
    ):
        """Should forward 1500 transactions intact, without truncating."""
        # Arrange
        mock_loader.load.return_value = large_transaction_set

        # Act
        report_engine.generate_report('bulk.csv', mock_mode)

        # Assert
        passed = mock_mode.process_transactions.call_args.args[0]
        assert len(passed) == 1500
        assert passed[0] == large_transaction_set[0]
        assert passed[-1] == large_transaction_set[-1]

    def test_special_characters_in_transaction_data(
        self, report_engine, mock_loader, mock_mode, transactions_with_special_chars
    ):
        """Should pass quotes, commas, and unicode through untouched."""
        # Arrange
        mock_loader.load.return_value = transactions_with_special_chars

        # Act
        report_engine.generate_report('special.csv', mock_mode)

        # Assert
        passed = mock_mode.process_transactions.call_args.args[0]
        assert passed[0]['description'] == 'Cafe "Le Marais", table 3'
        assert passed[2]['category'] == 'Café'

    def test_special_characters_in_filepath(
        self, report_engine, mock_loader, mock_mode
    ):
        """Should pass an awkward filepath to the loader unescaped."""
        # Arrange
        awkward_path = "/tmp/expenses (2024) — final & approved.csv"

        # Act
        report_engine.generate_report(awkward_path, mock_mode)

        # Assert
        mock_loader.load.assert_called_once_with(awkward_path)

    def test_mode_returning_empty_report_is_returned_as_is(
        self, report_engine, mock_loader, mock_mode, sample_transactions
    ):
        """Should return an empty report dict rather than substituting a default."""
        # Arrange
        mock_loader.load.return_value = sample_transactions
        mock_mode.process_transactions.return_value = {}

        # Act
        result = report_engine.generate_report('expenses.csv', mock_mode)

        # Assert
        assert result == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
