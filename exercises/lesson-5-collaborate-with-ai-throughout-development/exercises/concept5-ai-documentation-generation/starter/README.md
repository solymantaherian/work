# 💰 Expense Tracker CLI

Turn a spreadsheet of expenses into readable spending reports — from your terminal, with no setup beyond Python.

## Overview

Expense Tracker CLI reads your expenses from a CSV file and prints formatted reports that show where your money actually goes. It answers three questions: **which categories cost me the most?** (category report), **how does my spending change month to month?** (monthly report), and **what were my biggest single purchases?** (top report). It's built for anyone tracking personal or household spending — you export or type your expenses into a CSV, run one command, and read the result. No programming knowledge, no account, no internet connection, and no software to install beyond Python itself.

---

## 📦 Installation

### Prerequisites

- **Python 3.10 or higher.** Check your version:

  ```bash
  python3 --version
  ```

  You should see `Python 3.10.x` or higher. If the version is lower, the tool will fail to start with a `TypeError` about types — see [Troubleshooting](#python-version-errors).

- **No other software needed.** The tool uses only Python's standard library, so there is nothing to install with `pip` and no internet connection required.

> **Windows users:** if `python3` isn't recognized, use `python` instead of `python3` in every command below.

### Setup Steps

1. **Download the project** and move into its folder:

   ```bash
   git clone <repository-url>
   cd expense-tracker
   ```

   If you downloaded a ZIP file instead, unzip it and `cd` into the unzipped folder.

2. **Verify it works** by running the included sample data:

   ```bash
   python3 main.py examples/sample_expenses.csv
   ```

   If you see a table titled `Category Summary Report`, you're ready to go.

---

## 🚀 Quick Start

Run the tool against the sample expense file that ships with the project:

```bash
python3 main.py examples/sample_expenses.csv
```

**Expected output:**

```
Category Summary Report
==================================================
Category                    Total    Count        Avg
--------------------------------------------------
Shopping             $     575.00        2 $   287.50
Healthcare           $     500.00        2 $   250.00
Utilities            $     461.00        3 $   153.67
Food                 $     277.54        8 $    34.69
Transportation       $     265.00        3 $    88.33
Entertainment        $     164.99        2 $    82.50
--------------------------------------------------
TOTAL                $   2,243.53       20 $   112.18
```

Each row is one category: the total spent, how many purchases made it up, and the average purchase size. Categories are sorted largest-first, so your biggest spending area is always the top line.

---

## 📖 Usage

### Command Structure

```bash
python3 main.py <csv-file> [options]
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `<csv-file>` | Path to your expense CSV file. **Required.** | — |
| `--report <type>` | Which report to generate: `category`, `monthly`, or `top` | `category` |
| `--top-n <number>` | How many expenses the `top` report shows. Ignored by other reports. | `10` |
| `-h`, `--help` | Show built-in help and exit | — |

To see the built-in help at any time:

```bash
python3 main.py --help
```

### CSV Format Specification

Your file needs a **header row** naming four columns, followed by one row per expense:

```csv
date,amount,category,description
2025-01-05,52.30,Food,Weekly groceries
2025-01-10,85.00,Transportation,Gas
2025-01-12,150.00,Utilities,Internet bill
```

| Column | Required format | Good | Rejected |
|--------|-----------------|------|----------|
| `date` | `YYYY-MM-DD` | `2025-01-15` | `01/15/2025`, `15-Jan-2025` |
| `amount` | A positive number, digits only | `42.50`, `1200` | `$42.50`, `42.50 USD`, `-5.00`, `0` |
| `category` | Any text, cannot be blank | `Food` | *(empty)* |
| `description` | Any text, cannot be blank | `Weekly groceries` | *(empty)* |

**Things that are more flexible than you might expect:**

- **Column order doesn't matter.** The tool matches columns by their header name, so `description,category,amount,date` works exactly the same.
- **Extra columns are ignored.** If your bank export has a `notes` or `balance` column, you can leave it in place.
- **Spaces around values are trimmed.** `2025-01-15, 42.50, Food, Lunch` is fine.

**Things that will stop the run:**

- Every row must be complete. One bad row stops the whole report — the tool tells you the row number and fixes are quick.
- Amounts must be **positive**. This tool tracks spending, so refunds and `0.00` rows are rejected rather than subtracted.
- Category names are **case-sensitive**: `Food` and `food` become two separate categories in your report.

**If a description contains a comma, wrap it in double quotes:**

```csv
date,amount,category,description
2025-01-15,42.50,Food,"Coffee, with cream"
```

Without the quotes, the tool reads the description as just `Coffee` and silently drops everything after the comma. This is the one mistake that produces no error message, so it's worth checking.

---

## 📊 Examples

### Example 1 — Where does my money go? (category report)

The default report. Groups every expense by category, biggest first.

```bash
python3 main.py examples/sample_expenses.csv --report category
```

```
Category Summary Report
==================================================
Category                    Total    Count        Avg
--------------------------------------------------
Shopping             $     575.00        2 $   287.50
Healthcare           $     500.00        2 $   250.00
Utilities            $     461.00        3 $   153.67
Food                 $     277.54        8 $    34.69
Transportation       $     265.00        3 $    88.33
Entertainment        $     164.99        2 $    82.50
--------------------------------------------------
TOTAL                $   2,243.53       20 $   112.18
```

**Reading it:** Shopping tops the list on just 2 purchases averaging $287.50, while Food shows the opposite pattern — 8 purchases, but only $34.69 each. Large-and-rare and small-and-frequent are different budgeting problems, and the `Count` and `Avg` columns are what tell them apart.

---

### Example 2 — Is my spending going up? (monthly report)

```bash
python3 main.py examples/sample_expenses.csv --report monthly
```

```
Monthly Totals Report
==================================================
Month                  Total    Count        Avg
--------------------------------------------------
2025-01         $     816.79       10 $    81.68
2025-02         $   1,426.74       10 $   142.67
--------------------------------------------------
TOTAL           $   2,243.53       20 $   112.18
```

**Reading it:** Months run oldest to newest. February cost about $610 more than January despite the identical purchase count of 10 — so the increase came from buying *pricier* things, not more of them.

---

### Example 3 — What were my biggest purchases? (top report)

Use `--top-n` to choose how many to list.

```bash
python3 main.py examples/sample_expenses.csv --report top --top-n 5
```

```
Top 5 Expenses Report
================================================================================
Date               Amount Category             Description
--------------------------------------------------------------------------------
2025-02-18 $     450.00 Shopping             New laptop accessory
2025-02-03 $     320.00 Healthcare           Dentist appointment
2025-01-20 $     215.50 Utilities            Electric bill
2025-02-25 $     180.00 Healthcare           Prescription medications
2025-01-12 $     150.00 Utilities            Internet bill
--------------------------------------------------------------------------------
TOTAL (top 5)  $   1,315.50
```

**Reading it:** These 5 purchases account for $1,315.50 of the $2,243.53 total — roughly 59% of all spending across only 5 of 20 transactions.

If you ask for more expenses than the file contains, the tool shows all of them and adds a note rather than failing. Descriptions longer than 30 characters are shortened with `...` to keep the columns aligned.

---

### Example 4 — Using your own expenses

**Step 1.** Create a file named `my_expenses.csv` in any text editor (or export one from your bank and rename the columns to match):

```csv
date,amount,category,description
2025-03-01,45.00,Food,Grocery store
2025-03-02,120.00,Transportation,Monthly subway pass
2025-03-05,15.50,Food,Coffee and pastry
2025-03-08,85.00,Utilities,Electric bill
2025-03-10,200.00,Healthcare,Doctor visit
```

**Step 2.** Point the tool at it:

```bash
python3 main.py my_expenses.csv
```

```
Category Summary Report
==================================================
Category                    Total    Count        Avg
--------------------------------------------------
Healthcare           $     200.00        1 $   200.00
Transportation       $     120.00        1 $   120.00
Utilities            $      85.00        1 $    85.00
Food                 $      60.50        2 $    30.25
--------------------------------------------------
TOTAL                $     465.50        5 $    93.10
```

**Step 3.** Try the other reports on the same file:

```bash
python3 main.py my_expenses.csv --report monthly
python3 main.py my_expenses.csv --report top --top-n 3
```

The file can live anywhere — just give the full path if it's not in the current folder:

```bash
python3 main.py ~/Documents/budget/march.csv --report monthly
```

---

## 🔧 Troubleshooting

Every error message names the problem and, for data errors, the exact row number. Row numbers count the header as row 1, so **row 2 is your first expense** — the same number your spreadsheet shows.

### "File not found"

```
Error loading data: File not found: my_expenses.csv
```

The tool looked in the folder you ran the command from and found nothing by that name.

- List what's actually in the current folder: `ls` (macOS/Linux) or `dir` (Windows)
- Check the spelling, including the `.csv` ending. Windows may hide the extension, so a file shown as `my_expenses` may really be `my_expenses.csv.txt`.
- Use the full path instead: `python3 main.py /Users/you/Documents/my_expenses.csv`

---

### "Invalid date format"

```
Validation error: Row 2: Invalid date format '01/15/2025' (expected YYYY-MM-DD)
```

Dates must be year-month-day with dashes: `2025-01-15`. Write `2025-03-07`, not `2025-3-7`.

If your spreadsheet keeps reformatting dates, format the date column as **Text** before typing, or save from your spreadsheet with an explicit `YYYY-MM-DD` date format.

---

### "Invalid amount"

```
Validation error: Row 2: Invalid amount '$42.50' (must be a number)
```

Amounts must be bare numbers — no currency symbols, no thousands separators, no letters. Write `1200.00`, not `$1,200.00` or `1200 USD`.

A related message means the number parsed but wasn't a valid expense:

```
Validation error: Row 2: Amount must be positive, got -42.50
```

This tool totals spending, so every amount must be greater than zero. Remove refund and `0.00` rows rather than entering them as negatives.

---

### "CSV missing required columns"

```
Validation error: CSV missing required columns: category
```

The header row doesn't contain all four required names. Make sure the first line of the file spells each one exactly, in lowercase:

```csv
date,amount,category,description
```

The order is up to you and extra columns are fine — but all four names must be present and spelled correctly. `Date` or `amounts` will not be recognized.

---

### "Field is empty"

```
Validation error: Row 2: Category field is empty
```

Every expense needs all four values filled in. The usual cause is a row with a missing category or description, or a stray blank line in the middle of the file. Open the row named in the message and fill in the gap — if you're unsure, `Other` is a fine category.

---

### "No data to report"

```
No data to report: No valid transactions found in expenses.csv
```

The file was read successfully but contained no expense rows — usually a file with only a header. Check it has rows below line 1:

```bash
wc -l expenses.csv
```

A result of `1` means header only. Anything less than `2` means there's nothing to report on yet.

---

### "Invalid choice" for a report type

```
main.py: error: argument --report: invalid choice: 'yearly' (choose from 'category', 'monthly', 'top')
```

Only `category`, `monthly`, and `top` exist, and they're lowercase. For a yearly view, use `--report monthly` and read the months by year.

---

### <a id="python-version-errors"></a>Errors mentioning `TypeError` or `unsupported operand type(s) for |`

Your Python is older than 3.10. Check it:

```bash
python3 --version
```

Install a newer Python from [python.org/downloads](https://www.python.org/downloads/), then try again. If you have several versions installed, name the one you want explicitly:

```bash
python3.12 main.py examples/sample_expenses.csv
```

---

### "command not found: python3"

Python isn't installed, or isn't on your PATH. On Windows, try `python` instead. If that also fails, install Python from [python.org/downloads](https://www.python.org/downloads/) and — on Windows — tick **"Add Python to PATH"** in the installer.

---

### The report runs, but the numbers look wrong

The tool only reports what's in the file, so surprises usually trace back to the data:

- **A category appears twice.** Names are case- and spelling-sensitive: `Food`, `food`, and `Foods` are three separate categories. Pick one spelling and use it everywhere.
- **A description got cut short.** An unquoted comma truncates it — `Coffee, with cream` becomes `Coffee`. Wrap descriptions containing commas in double quotes.
- **A total is far too large.** Look for a missing decimal point — `4250` instead of `42.50`. The `top` report is the fastest way to spot one.
- **A month is missing entirely.** No expenses were recorded for it. Months with no data don't appear as zero rows.

---

## 💡 Tips

1. **Keep one canonical list of categories** and reuse the exact spellings. Broad ones like `Food`, `Transportation`, and `Utilities` are more useful than a long tail of near-duplicates.
2. **Add expenses as they happen** rather than reconstructing a month from memory — the monthly report is only as honest as the data behind it.
3. **Write descriptions you'll recognize later.** `Costco run` beats `groceries` when a $300 line shows up in the `top` report.
4. **Start from the sample file.** Copy `examples/sample_expenses.csv`, delete the rows, and keep the header — the format will already be correct.
5. **Back up your CSV.** It's a plain text file; a copy in cloud storage or version control protects years of tracking.

---

## Getting Help

```bash
python3 main.py --help
```

If something isn't working, confirm the basics in order: `python3 --version` reports 3.10 or higher, you're in the project folder, and the sample file still runs:

```bash
python3 main.py examples/sample_expenses.csv
```

If the sample works but your file doesn't, the problem is in the CSV — and the error message names the row to look at.
