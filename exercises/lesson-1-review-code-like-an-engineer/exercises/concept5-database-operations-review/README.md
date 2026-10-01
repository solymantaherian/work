# Concept 5: Database Operations Review

## Exercise Overview

Review database operations code that demonstrates basic SQL injection vulnerabilities and simple structural issues. This builds on the security awareness from Concept 2.

## Learning Objectives

- Identify SQL injection vulnerabilities
- Recognize basic input validation issues  
- Apply systematic code review skills
- Understand database security basics

## Instructions

### Step 1: Run Tests to See the Issues
```bash
cd concept5-database-operations-review/starter
python -m pytest test_database_security.py -v
```

**Expected Output:**
- Basic functionality tests pass
- Security tests FAIL (demonstrating SQL injection!)
- Shows database security vulnerabilities

### Step 2: Review the Code
1. **Open** `starter/database_manager.py` and review the functions
2. **Apply** the engineering code review framework:
   - Structure & Organization
   - Naming & Clarity
   - Error Handling
   - Security Issues
3. **Document** your findings using the template below

### Step 3: Run the Solution Tests
```bash
cd ../solution
python -m pytest test_secure_database.py -v
```

**Expected Output:**
- All tests pass showing fixes work
- SQL injection is now blocked
- Notice improved parameterized queries

### Step 4: Compare and Learn
4. **Compare** your analysis with the improved code

## Review Template

### Issues Found

> **Note:** The current `starter/database_manager.py` has already been hardened past the
> `solution/` file — all three queries are parameterized, so **there is no SQL injection
> present**. The findings below are the issues that remain.

**Structure & Organization:**
- [x] Issue 1: ~40 lines of duplicated `connect` / `try` / `rollback` / `finally` boilerplate across the three public methods (`starter/database_manager.py:92-116`, `:138-179`, `:201-247`). Extract a single `@contextmanager _connect()` helper.
- [x] Issue 2: `logging.basicConfig(level=logging.ERROR)` runs at module import (`:24`). A library module reconfiguring the root logger overrides whatever the host application set up, and it makes every `logger.info` call in this file dead code. Use `logger.addHandler(logging.NullHandler())` instead.
- [x] Issue 3: `SELECT *` (`:97`) returns every column to every caller, including any `password_hash` / `reset_token` column added later. Name the columns explicitly.
- [x] Issue 4: No `db_path` validation in `__init__` (`:28-29`). `sqlite3.connect` creates the file when missing, so a typo'd path silently produces an empty database and every call then fails as `no such table: users`.

**Naming & Clarity:**
- [x] Issue 1: Docstrings promise `TypeError` for non-string input, but the validators raise `ValueError` for that case — see Error Handling Issue 3.
- [x] Issue 2: `get_user_by_email` returns a positional tuple. Set `conn.row_factory = sqlite3.Row` so callers use column names instead of indexes.

**Error Handling:**
- [x] Issue 1: **Everything collapses to bare `Exception`** (`:108`, `:113`, `:158`, `:166`, `:174`, `:226`, `:234`, `:242`). A caller cannot distinguish a duplicate email (user-fixable, HTTP 409) from a locked database (retryable, 503) from real corruption (500) without string-matching the message. This is the most significant structural problem in the file.
- [x] Issue 2: No exception chaining — every `raise Exception(msg)` discards the original traceback. Should be `raise DatabaseError(msg) from e`.
- [x] Issue 3: Validation check order contradicts the docstrings (`:33-37`, `:50-54`). `if not email:` runs *before* the `isinstance` check, so `_validate_email(0)`, `_validate_email([])` and `_validate_name(0)` raise `ValueError`, not the documented `TypeError`. The type check must come first.
- [x] Issue 4: `conn.rollback()` inside `except` and `conn.close()` inside `finally` can themselves throw, masking the original exception.
- [x] Issue 5: `user_id` has no upper bound, so a Python bigint reaches `cursor.execute` and raises `OverflowError` — which none of the `sqlite3.Error` handlers catch and no docstring mentions.

**Security Issues:**
- [x] Issue 1: **Email regex accepts a trailing newline** (`:44-45`). `re.match` with `$` matches before a final `\n`, so `"a@b.co\n"` passes validation (verified). That newline reaches the database and any downstream consumer — mail headers, log lines, CSV exports — which is the injection vector for those sinks. Use `re.fullmatch`, or `\Z` instead of `$`.
- [x] Issue 2: **Raw driver errors propagated to callers** (`:106-113`, `:156-174`, `:224-242`). `raise Exception(f"...: {e}")` embeds SQLite's message, which can include table/column names and the database file path — schema disclosure if a web layer renders it.
- [x] Issue 3: **PII in logs and exception text** (`:46`, `:101`, `:149`). Email addresses are written into log records and into the `ValueError` raised on failed validation. Log the user ID, or redact to `a***@domain`.
- [x] Issue 4: **`bool` passes the `int` type check** (`:68`). `isinstance(True, int)` is `True`, so `update_user_email(True, "x@y.co")` silently updates user ID 1.
- [x] Issue 5: **No email normalization.** `_validate_email` never case-folds and `create_user` never strips `name`, so `A@Example.com` and `a@example.com` both insert past a `UNIQUE(email)` index — duplicate-account confusion.
- [x] Issue 6: Regex accepts consecutive dots in the domain (`a@b..co`, verified). Minor.

### Specific Recommendations

1. **SQL Injection:** None required — `:97`, `:143` and `:206` all use `?` placeholders with a parameter tuple, which is correct. Keep it that way; never build these strings with f-strings or `%`.
2. **Input Validation:** Switch the regex to `re.fullmatch` to close the trailing-newline bypass; move the `isinstance` check ahead of the falsy check in both validators; reject `bool` explicitly with `if isinstance(user_id, bool) or not isinstance(user_id, int)`; normalize email to lowercase and `.strip()` the name before insert; bound `user_id` to 64 bits; validate `db_path` in `__init__`.
3. **Connection Management:** Replace the three copies of the boilerplate with one `@contextmanager _connect()` that passes `timeout=10.0` (the 5s default surfaces as `database is locked` under concurrency), runs `PRAGMA foreign_keys = ON` (off by default in SQLite), sets `row_factory = sqlite3.Row`, and closes in `finally`.
4. **Error Handling:** Define a small hierarchy — `DatabaseError`, `DuplicateEmailError`, `ConnectionFailedError` — and raise those with `from e`. Log the driver detail with `exc_info=True`, but raise a generic message to the caller so schema details stay out of responses.

### Overall Assessment

- **Quality Rating:** **Good** — parameterized queries throughout, real validation with RFC-backed limits, connections closed in `finally`, rollback on every write failure, and accurate docstrings. Held back from Excellent by the exception design, the triplicated boilerplate, and the validation-ordering bugs.
- **Security Rating:** **Low Risk** — no injection path and no leaked connections. The residual exposure is the newline bypass and the error/log disclosure, neither of which is directly exploitable against the database itself.
- **Recommendation:** **Modify**
- **Reasoning:** Nothing here is a release blocker. Before merge, take the three cheap correctness fixes (`re.fullmatch`, bool rejection, type-check ordering) plus the custom exception hierarchy — the `raise Exception` pattern is the hardest thing to retrofit once callers start depending on it. The `_connect()` context manager and log redaction can follow immediately after.

## Key Learning Points

- SQL injection occurs when user input is directly concatenated into queries
- Parameterized queries prevent SQL injection attacks
- Input validation should happen before database operations
- Database connections should be properly managed and closed

## Common Issues to Look For

1. **String concatenation** in SQL queries instead of parameterized queries
2. **No input validation** for user-provided data
3. **Missing error handling** for database operations
4. **Connection leaks** from unclosed database connections
5. **Generic exception handling** that hides specific database errors

After completing your review, check the solution to see the improved version with parameterized queries, proper input validation, and secure database practices.