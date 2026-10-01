# Concept 4: API Error Handling Review

## Learning Objective
Learn to identify and fix error handling issues in API client code, focusing on network errors, HTTP status codes, retry behaviour, exception-handler ordering, and user-friendly error messages.

## Exercise Status

> **Note:** `starter/api_client.py` has been revised since this exercise was written. It now includes
> timeouts, a retry loop, and exponential backoff, so it no longer exhibits the original "crashes on
> network error / returns None" problems. Two consequences:
>
> - `starter/test_api_errors.py` is **out of date — 8 of its 13 tests fail** against the current starter,
>   because they assert the old behaviour (`result is None`, timeouts propagating uncaught).
> - `solution/api_client.py` has **not** been revised to match, and is now less resilient than the
>   starter on some axes (no retries, no backoff, hardcoded `timeout=5`).
>
> The review targets below describe the **current** starter code and have been verified against it.
> See [Known Exercise Drift](#known-exercise-drift) for details.

## Background
API clients need proper error handling to provide good user experience and prevent crashes. Common issues include:
- Unhandled network timeouts and connection errors
- Poor HTTP status code handling
- Exception handlers ordered so that narrower ones are unreachable
- Retry policies that miss the statuses most worth retrying (429, 503)
- Dead policy helpers that look authoritative but are never called
- Missing input validation and URL encoding
- Bare `Exception` raises that callers cannot branch on

## Exercise Structure

### Starter Code (`starter/`)
- **File**: `api_client.py` - API client with error handling and structural problems
- **Issues**: Unreachable JSON error handler, rate limits never retried, unused retry-policy helper, no input validation or URL encoding, bare `Exception` raises, ~40 lines duplicated across two methods
- **Test File**: `test_api_errors.py` - **currently failing (8/13)**; asserts pre-revision behaviour

### Solution Code (`solution/`)
- **File**: `api_client.py` - Client demonstrating structured error handling and input validation
- **Improvements**: Try/except for network errors, per-status-code branches (404/401/5xx), structured error dictionaries, constructor and parameter validation, `json=` parameter, `base_url` trailing-slash normalization
- **Not addressed by the solution**: retries/backoff, 429 and `Retry-After`, URL encoding of path segments, custom exception types, de-duplication of the two methods. Issues 1-3 and 8-9 below have no counterpart in the solution file.
- **Test File**: `test_api_improvements.py` - 19 tests, all passing

## How to Run

### Test the Starter Code (Shows Problems)
```bash
cd starter/
python api_client.py
pytest test_api_errors.py -v    # expect 8 failures - see Exercise Status above
```

### Test the Solution Code (Shows Fixes)
```bash
cd solution/
python api_client.py
pytest test_api_improvements.py -v
```

> `python api_client.py` in either directory makes real network calls to `httpbin.org` and to a
> deliberately unresolvable domain. The starter's retry loop sleeps between attempts, so the
> network-error demo takes a few seconds to complete.

## Key Issues to Find

Line references are to the current `starter/api_client.py`.

### Blockers

#### 1. Unreachable JSON error handler (`:94`)
- **Problem**: `requests.exceptions.JSONDecodeError` subclasses *both* `RequestException` and `json.JSONDecodeError`. Because `except requests.RequestException` (`:91`) is listed first, it always wins and the `json.JSONDecodeError` clause is dead code. Malformed JSON reports "An unexpected error occurred while making the request" instead of the specific message written for it.
- **Fix**: Order `except` clauses narrowest-first — move the `json.JSONDecodeError` clause above `RequestException`.
- **Teaching point**: `except` clauses are evaluated in source order, not by specificity.

#### 2. HTTP 429 is never retried (`:69-71`, `:118-120`)
- **Problem**: 429 Too Many Requests falls into the `else` "client error, don't retry" branch and raises on the first attempt. Rate limiting is the case where backoff is most clearly correct. The `Retry-After` response header is also ignored.
- **Fix**: Retry 429 and 503; prefer `Retry-After` over the computed backoff delay when the header is present.

#### 3. `_should_retry` is dead code (`:35-46`)
- **Problem**: Defined and documented, but never called. The retry decision is inlined and duplicated in four places instead.
- **Fix**: Route all retry decisions through the helper.
- **Teaching point**: An unused policy function is worse than none — editing it to add 429 changes nothing at runtime, and unit tests of it pass while production behaviour is unaffected.

### Should Fix

#### 4. Path segments interpolated without validation or encoding (`:49`, `:98`)
- **Problem**: `user_id` goes straight into the URL. `get_user_data("../../admin/secrets")` produces `https://api.example.com/users/../../admin/secrets`. `base_url` is unvalidated too — a trailing slash yields `//users/1`, and an `http://` scheme sends the bearer token in plaintext. An empty `api_key` sends a bare `Bearer `.
- **Fix**: Validate parameters, and pass path segments through `urllib.parse.quote(str(user_id), safe="")`. Validate `base_url` scheme and strip trailing slashes.

#### 5. Only HTTP 200 counts as success (`:58`, `:107`)
- **Problem**: A `PUT` returning 204 No Content — a normal success — is treated as a client error and raises.
- **Fix**: Test `response.ok`, or `200 <= status < 300`.

#### 6. `max_retries = 0` silently returns `None` (`:54`, `:103`)
- **Problem**: `range(0)` never enters the loop, so the method falls off the end and returns `None` without sending a request — indistinguishable from a successful empty response.
- **Fix**: Validate `max_retries >= 1` and `timeout > 0` in `__init__`. Note also that `max_retries=3` yields three *total* attempts (1 + 2 retries), which does not match the name.

#### 7. Everything raises bare `Exception`
- **Problem**: Callers cannot distinguish "user not found" from "network unreachable" from "server error" without string-matching the message, and the status code is not recoverable programmatically.
- **Fix**: Define a small hierarchy (`APIError` → `APINotFound`, `APIServerError`, `APINetworkError`) carrying `status_code` and the response.
- **Teaching point**: This is the issue with the largest blast radius on calling code, and the most expensive to defer.

#### 8. ~40 lines duplicated between the two methods
- **Problem**: `get_user_data` and `update_user` differ only in verb, body, and return value. Every fix above must be applied twice, and issues 1, 2, and 5 are already inconsistently exposed across the two copies.
- **Fix**: Collapse to a single `_request(method, path, **kwargs)` helper holding the retry, backoff, and error-mapping logic.

#### 9. `TypeError` from `json.dumps` escapes unhandled (`:105`)
- **Problem**: No handler catches `TypeError`, so passing non-serializable data produces a raw traceback. The payload is also re-serialized on every retry attempt.
- **Fix**: Serialize once before the loop, or use `json=data` and let `requests` set `Content-Type`.

### Nice to Have

- **No jitter in backoff** (`:33`) — fixed `1s, 2s, 4s` means many clients recovering from one outage retry in lockstep.
- **No `requests.Session`** — module-level `requests.get`/`put` forces a fresh TCP + TLS handshake per call.
- **`response.text` interpolated unbounded** (`:62`, `:71`) — a large HTML error page becomes the exception message, and response bodies land in logs. Truncate.
- **`last_exception` written but never read** (`:74`, `:83`) — those branches raise a fresh `Exception` instead.
- **No logging** — retries and backoff sleeps are invisible to operators.
- **No overall deadline** — worst case is ~33s of blocking (3 × 10s timeout + 3s of sleeps) with no total budget.
- **Inconsistent return types** — `dict` from `get_user_data` vs bare `True` from `update_user`, which also discards the server's response body.

## Code Review Questions

When reviewing the starter code, consider:

1. **Error Handling**: What happens when network requests fail? Which handlers can actually be reached?
2. **Handler Ordering**: For each `except` clause, is a broader clause listed above it?
3. **Status Codes**: Which statuses are retried, and which should be? Is 429 handled correctly?
4. **Dead Code**: Is every helper method actually called?
5. **User Experience**: Do users get helpful error messages? Can callers branch on failure type without parsing strings?
6. **Input Validation**: Are parameters validated and encoded before being placed in a URL?
7. **Return Values**: Can any code path return `None` or fall off the end silently?
8. **Duplication**: How many places would a single fix need to be applied?

## Expected Learning Outcomes

After completing this exercise, you should be able to:
- Identify missing and unreachable network error handling in API clients
- Order exception handlers correctly when exception types have overlapping inheritance
- Recognize retry policies that omit the statuses most worth retrying, and honour `Retry-After`
- Spot dead policy helpers and silent `None`-returning code paths
- Design custom exception hierarchies that callers can branch on
- Validate and URL-encode parameters before interpolating them into request paths
- Recognize when duplication between methods is what makes every other defect a two-site fix

## Known Exercise Drift

Recorded so the next person does not re-diagnose it. Verified 2026-09-10.

| Artifact | State | Detail |
| --- | --- | --- |
| `starter/api_client.py` | Revised | Gained `timeout`, `max_retries`, exponential backoff, `raise ... from e` |
| `starter/test_api_errors.py` | **Stale** | 8/13 fail; assert `result is None` and uncaught timeouts |
| `README.md` | Updated | This file — review targets now match the current starter |
| `solution/api_client.py` | **Stale** | No retries/backoff/429 handling; hardcoded `timeout=5` |
| `solution/test_api_improvements.py` | Passing | 19/19, but only covers the pre-revision issue set |

Failing starter tests: `test_successful_request_works`, `test_network_timeout_crashes_program`,
`test_connection_error_crashes_program`, `test_404_returns_none_without_info`,
`test_401_returns_none_without_info`, `test_500_returns_none_without_info`,
`test_update_failure_gives_no_info`, `test_update_network_error_crashes_program`.

To restore the exercise, either roll `starter/api_client.py` back to the naive version the tests and
solution assume, or rewrite `test_api_errors.py` and `solution/api_client.py` around the issue set
above. The second is the better exercise — issues 1-3 are subtler and more instructive than the
original "no try/except" problems — but it is the larger change.
