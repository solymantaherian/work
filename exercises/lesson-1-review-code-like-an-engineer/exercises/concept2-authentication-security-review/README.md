# Concept 2: Authentication Security Review

## Exercise Overview

Review an authentication system for security and structural issues. Apply systematic code review skills to identify potential problems with security, architecture, and implementation.

## Learning Objectives

- Apply systematic security analysis
- Identify authentication implementation issues
- Recognize structural and coupling problems
- Practice security-focused code review

## Instructions

### Step 1: Run Tests to See the Issues
```bash
cd concept2-authentication-security-review/starter
pytest test_security_vulnerabilities.py -v
```

**Expected Output:**
- Basic functionality tests pass
- Security tests reveal potential issues
- Tests demonstrate various authentication patterns

### Step 2: Security Review
1. **Open** `starter/user_auth.py` and examine the security flaws
2. **Focus on security issues** - this is a security-critical component
3. **Apply** the engineering framework with extra attention to:
   - SQL injection vulnerabilities (line 27!)
   - Password handling (plain text storage!)
   - Input validation (none!)
   - Error handling

### Step 3: Run Security Tests on Secure Solution
```bash
cd ../solution
pytest test_secure_authentication.py -v
```

**Expected Output:**
- All security tests pass
- SQL injection attempts are blocked
- Passwords are properly hashed
- Input validation works correctly

### Step 4: Document Security Issues
4. **Document** all security vulnerabilities found
5. **Compare** with the secure implementation

## Review Template

> **Read first — this README's premise is stale.** The starter is already hardened against the two vulnerabilities advertised above: `starter/user_auth.py:28-31` uses a parameterized query, and `:36` / `:56-61` use bcrypt with per-password salts. As a result `test_security_vulnerabilities.py` has **2 failing tests** — `test_sql_injection_authentication_bypass` asserts a bypass that no longer occurs, and `test_plain_text_password_storage` queries a `password` column that does not exist (the schema at `:51` names it `password_hash`). The starter also cannot be imported without `pip install bcrypt`. The findings below describe the code as it actually is; line refs are `starter/user_auth.py`.

### Critical Security Issues

**SQL Injection:**
- [x] Issue: **Not present.** `:28-31` binds `username` as a query parameter (`WHERE username=?`), so the driver escapes it. Verified: `admin' OR '1'='1` returns `None`.
- [x] Impact: None from injection. The residual risk is `SELECT *` combined with positional unpacking (`user[2]`, `:35`) — if the schema at `:47-53` gains a column, `user[2]` silently reads the wrong field and hands a non-hash value to `checkpw`. The comment at `:34` documenting the tuple order is itself the warning sign.
- [x] Fix: Keep the parameterized query; replace `SELECT *` with an explicit `SELECT id, password_hash` so column order stops being load-bearing.

**Password Security:**
- [x] Issue: The hashing is sound (bcrypt with `gensalt()` at `:56`, `:60`), but **two accounts with known passwords are hardcoded in the module** — `admin`/`password123` and `user1`/`secret` at `:56-61`, seeded by `connect_to_database()` on every instantiation. Separately, `:36` passes an unbounded password to `bcrypt.checkpw`, which rejects anything over 72 bytes.
- [x] Risk Level: **Critical** — not for the algorithm, but because fixture credentials live in the production code path. Anyone importing this module gets a working `admin` login.
- [x] Recommendation: Move seeding into a test fixture; never ship credential inserts inside the module that performs authentication. Truncate or reject over-72-byte passwords before calling bcrypt.

**Input Validation:**
- [x] Missing validation: No type or length check on either argument (`:27`). Verified: `password=None` → `AttributeError: 'NoneType' object has no attribute 'encode'`; `password=12345` → the same; `admin` plus a 10,000-byte password → `ValueError: password cannot be longer than 72 bytes`.
- [x] Attack vector: **Username enumeration via the error channel.** An over-length password returns `None` for an unknown user but raises `ValueError` for a real one, so an attacker separates valid usernames by response type alone. The same unhandled exceptions reach the caller as a 500 with a traceback, and the `AttributeError` path turns any malformed client request into a crash.

### Structural Issues

**Code Architecture:**
- [x] Coupling issues: `__init__` (`:24-25`) calls the module-level `connect_to_database()` directly, leaving no injection point — `UserAuth` cannot be tested against a fixture, aimed at a real database, or handed a connection pool without editing the class. Every instantiation builds a fresh in-memory schema, so the class is hardwired to its own mock.
- [x] Separation of concerns: One module carries the auth policy, the connection factory, the schema DDL, the test-data seeding, and the token generator (`:23-68`). `db_connection` is a public attribute, so callers bypass `login` and query the users table directly. Token generation belongs behind a session service rather than in a module-level helper.

**Error Handling:**
- [x] Information leakage: **Timing oracle, measured at 20,211×.** An unknown username returns in 0.01 ms; a known username with a wrong password takes 254 ms, because only that path reaches `bcrypt.checkpw` (`:33-36`). Valid usernames are separable with a stopwatch — no statistical analysis required. Fix: always run `checkpw` against a fixed dummy hash when the user is absent, so both paths cost the same.
- [x] Missing error cases: No `try`/`except` anywhere — `sqlite3.Error` from `:28`, `AttributeError` from `:36`, and bcrypt's `ValueError` all propagate raw. No rate limiting or account lockout (`test_no_rate_limiting` runs 100 attempts unimpeded; the suite's 34 s runtime is bcrypt's cost, not a control). No audit logging of success or failure. **Sessions are not managed at all:** the token at `:37-38` is returned and immediately discarded — verified that `UserAuth` holds only `db_connection`, so there is no store, no expiry, no revocation, and no way for a later request to validate the token it was given.

### Overall Security Assessment

- **Security Rating:** **High Risk**
- **Primary Concerns:**
  1. **Hardcoded credentials** — `admin`/`password123` seeded into the module on every instantiation (`:56-61`).
  2. **Predictable session tokens** — `random.choice` (`:68`) is Mersenne Twister, not a CSPRNG. Verified reproducible under a fixed seed, so tokens are derivable from observed output rather than unguessable. The 32-character length is not the weakness; the generator is.
  3. **Username enumeration** through two independent channels — timing (20,211×) and error type (`ValueError` vs `None`).
- **Recommendation:** **Major Refactoring Required.** Not a reject: the cryptographic core is correct and every fix below is additive rather than a redesign.
- **Immediate Actions Required:**
  1. Replace `random` with `secrets.token_urlsafe` in `generate_random_string` (`:66-68`).
  2. Delete the seeded test accounts from `connect_to_database` (`:54-61`).
  3. Validate the type and length of both arguments before use, and equalize the absent-user path with a dummy bcrypt check.
  4. Inject the connection through `__init__`; make `db_connection` private.
  5. Add a session store with expiry, per-account rate limiting, and audit logging before any deployment.

### Note on the Provided Solution

`solution/user_auth.py:44` hashes with **unsalted SHA-256** while the starter already uses **bcrypt** — so on password storage the "secure" solution is a regression, not an improvement. SHA-256 is a fast hash: it is GPU-crackable at billions of guesses per second and, without a salt, vulnerable to rainbow tables. The solution's own comment at `:42-43` concedes that production should use bcrypt or Argon2. It does fix token generation (`secrets`, `:21`), add input validation (`:46-55`), and add a `register_user` path, and its 8 tests pass — but adopt those parts, not its password hashing.

## Critical Vulnerabilities to Find

1. **SQL Injection** via string concatenation in database queries
2. **Plain text password storage** and comparison
3. **No input validation** allowing malicious input
4. **Information disclosure** through error messages
5. **Tight coupling** between database and authentication logic

## Security Best Practices (from Solution)

- Use parameterized queries to prevent SQL injection
- Hash passwords with strong algorithms (PBKDF2, bcrypt, Argon2)
- Implement proper input validation and sanitization
- Use dependency injection for better testing and security
- Add rate limiting to prevent brute force attacks
- Implement proper session management
- Add comprehensive audit logging

## Real-World Impact

The vulnerabilities in this code could lead to:
- Complete database compromise
- User account takeovers
- Data breaches
- Credential theft
- System-wide security failures

After your review, examine the solution to understand how to implement secure authentication with proper password hashing, parameterized queries, and comprehensive security measures.