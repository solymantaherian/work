"""
Secure user authentication.

Refactored against the review in ../README.md. Each change is tagged with the
finding it closes:

  [F1] Predictable session tokens  -> secrets, not random (Mersenne Twister)
  [F2] Hardcoded credentials       -> no seeding in the connection factory
  [F3] Input validation            -> type/length checks before any DB access
  [F4] Timing oracle (20,211x)     -> absent user still pays a bcrypt check
  [F5] Enumeration via error type  -> validation runs before the user lookup
  [F6] Tight coupling              -> connection injected, attribute private
  [F7] No session management       -> token store with expiry and revocation
  [F8] No rate limiting            -> per-account sliding-window lockout
  [F9] No audit trail              -> structured logging of every outcome
  [F10] SELECT * + user[2]         -> explicit column list
  [F11] Unhandled backend errors   -> wrapped, detail kept server-side
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import sqlite3
import time
from dataclasses import dataclass

import bcrypt

logger = logging.getLogger(__name__)

# --- Policy constants: named so tests can derive expectations from the rule ---
BCRYPT_ROUNDS = 12
MAX_USERNAME_LENGTH = 254
MAX_PASSWORD_BYTES = 72  # bcrypt's hard ceiling; longer input is rejected, never truncated
TOKEN_BYTES = 32  # -> 43-character urlsafe token
SESSION_TTL_SECONDS = 30 * 60
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash BLOB NOT NULL
)
"""

# [F4] A real hash of a value nobody knows, so the "no such user" branch costs
# the same as the "wrong password" branch. Computed at import (~0.25s, once) at
# the same cost factor as live hashes -- a cheaper dummy would reintroduce the
# timing difference it exists to remove. This is not a credential: the plaintext
# is discarded and never compared against anything.
_DUMMY_HASH = bcrypt.hashpw(
    secrets.token_urlsafe(32).encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)
)


class AuthError(Exception):
    """Base class for authentication failures the caller should handle."""


class InvalidCredentialFormat(AuthError, ValueError):
    """Username or password is the wrong type, empty, or over length."""


class UsernameTaken(AuthError):
    """Registration hit the UNIQUE constraint on username."""


class AuthBackendError(AuthError):
    """The credential store is unreachable or returned an error."""


@dataclass(frozen=True)
class Session:
    """An issued session. The raw token is deliberately not stored here."""

    user_id: int
    username: str
    created_at: float
    expires_at: float


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the users table if it does not exist."""
    connection.execute(SCHEMA)
    connection.commit()


def connect_to_database(database: str = ":memory:") -> sqlite3.Connection:
    """
    Open a connection and ensure the schema exists.

    [F2] Seeds no accounts. The previous version inserted admin/password123 and
    user1/secret on every call, putting working credentials in the import path.
    """
    connection = sqlite3.connect(database)
    create_schema(connection)
    return connection


def generate_session_token() -> str:
    """
    [F1] Cryptographically secure token.

    The previous version used random.choice over ascii_letters. Mersenne Twister
    is not a CSPRNG: its internal state is recoverable from observed output, so
    tokens were predictable regardless of length.
    """
    return secrets.token_urlsafe(TOKEN_BYTES)


def _token_key(token: str) -> str:
    """
    Index sessions by digest, not by the token itself, so a dump of the session
    store yields no usable tokens.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class UserAuth:
    """
    Authenticates users and issues session tokens.

    [F6] The connection is injected. It defaults to a fresh in-memory database
    so the class stays runnable, but the seam means tests, a real database, and
    a pooled connection are all reachable without editing this class.

    `now` is injected for the same reason: expiry and lockout are testable
    without sleeping.
    """

    def __init__(
        self,
        db_connection: sqlite3.Connection | None = None,
        *,
        now=time.monotonic,
    ) -> None:
        self._owns_connection = db_connection is None
        self._db = connect_to_database() if self._owns_connection else db_connection
        self._now = now
        self._sessions: dict[str, Session] = {}
        self._failed_attempts: dict[str, list[float]] = {}

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the connection only if this instance opened it."""
        self._sessions.clear()
        if self._owns_connection:
            self._db.close()

    def __enter__(self) -> UserAuth:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- public API --------------------------------------------------------

    def register_user(self, username: str, password: str) -> int:
        """Create a user and return its id. Raises UsernameTaken on collision."""
        self._validate_credential_format(username, password)

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)
        )
        try:
            cursor = self._db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            self._db.commit()
        except sqlite3.IntegrityError:
            # Distinguishable by design: a registration form has to say the name
            # is taken. Gate this behind email verification if the username
            # space itself must stay private.
            logger.info("auth.register.conflict username=%r", username)
            raise UsernameTaken("username already registered") from None
        except sqlite3.Error:
            logger.exception("auth.register.backend_error username=%r", username)
            raise AuthBackendError("credential store unavailable") from None

        logger.info("auth.register.ok username=%r user_id=%s", username, cursor.lastrowid)
        return cursor.lastrowid

    def login(self, username: str, password: str) -> str | None:
        """
        Verify credentials and return a session token, or None on any failure.

        [F5] Format validation runs before the lookup, so a malformed request
        fails identically whether or not the account exists. Every rejection
        after that point returns a bare None: wrong password, unknown user, and
        locked-out are indistinguishable to the caller and separated only in the
        audit log.
        """
        self._validate_credential_format(username, password)

        if self._is_locked_out(username):
            logger.warning("auth.login.locked_out username=%r", username)
            return None

        row = self._lookup_user(username)

        # [F4] Both branches run one bcrypt check at the same cost factor.
        stored_hash = row[1] if row is not None else _DUMMY_HASH
        password_matches = bcrypt.checkpw(password.encode("utf-8"), stored_hash)

        if row is None or not password_matches:
            self._record_failure(username)
            logger.warning(
                "auth.login.failed username=%r account_exists=%s attempts=%d",
                username,
                row is not None,
                len(self._failed_attempts.get(username, [])),
            )
            return None

        self._failed_attempts.pop(username, None)
        token = self._issue_session(user_id=row[0], username=username)
        logger.info("auth.login.ok username=%r user_id=%s", username, row[0])
        return token

    def validate_session(self, token: str) -> Session | None:
        """[F7] Resolve a token to its session, or None if unknown or expired."""
        if not isinstance(token, str) or not token:
            return None

        key = _token_key(token)
        session = self._sessions.get(key)
        if session is None:
            return None

        if self._now() >= session.expires_at:
            del self._sessions[key]
            logger.info("auth.session.expired username=%r", session.username)
            return None

        return session

    def logout(self, token: str) -> bool:
        """[F7] Revoke one session. True if a live session was removed."""
        if not isinstance(token, str) or not token:
            return False
        session = self._sessions.pop(_token_key(token), None)
        if session is not None:
            logger.info("auth.logout username=%r", session.username)
        return session is not None

    def revoke_all_sessions(self, username: str) -> int:
        """[F7] Revoke every session for one user. Returns the count removed."""
        doomed = [k for k, s in self._sessions.items() if s.username == username]
        for key in doomed:
            del self._sessions[key]
        if doomed:
            logger.info("auth.revoke_all username=%r count=%d", username, len(doomed))
        return len(doomed)

    # -- internals ---------------------------------------------------------

    def _validate_credential_format(self, username: str, password: str) -> None:
        """
        [F3] Reject malformed input before it reaches the database or bcrypt.

        The previous version crashed with AttributeError on a non-string
        password and raised bcrypt's ValueError on anything over 72 bytes --
        the latter only for usernames that existed, which leaked their
        existence.
        """
        if not isinstance(username, str) or not isinstance(password, str):
            raise InvalidCredentialFormat("username and password must be strings")
        if not username or not password:
            raise InvalidCredentialFormat("username and password must be non-empty")
        if len(username) > MAX_USERNAME_LENGTH:
            raise InvalidCredentialFormat(
                f"username exceeds {MAX_USERNAME_LENGTH} characters"
            )
        # Byte length, not character count: one emoji is four bytes to bcrypt.
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise InvalidCredentialFormat(
                f"password exceeds {MAX_PASSWORD_BYTES} bytes"
            )

    def _lookup_user(self, username: str) -> tuple[int, bytes] | None:
        """
        [F10] Explicit columns, so schema changes cannot silently shift what
        gets passed to checkpw. [F11] Backend errors are logged with detail and
        re-raised without it.
        """
        try:
            return self._db.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("auth.lookup.backend_error username=%r", username)
            raise AuthBackendError("credential store unavailable") from None

    def _issue_session(self, *, user_id: int, username: str) -> str:
        token = generate_session_token()
        issued_at = self._now()
        self._sessions[_token_key(token)] = Session(
            user_id=user_id,
            username=username,
            created_at=issued_at,
            expires_at=issued_at + SESSION_TTL_SECONDS,
        )
        return token

    def _recent_failures(self, username: str) -> list[float]:
        """Drop attempts that have aged out of the window."""
        cutoff = self._now() - LOCKOUT_WINDOW_SECONDS
        recent = [t for t in self._failed_attempts.get(username, []) if t > cutoff]
        if recent:
            self._failed_attempts[username] = recent
        else:
            self._failed_attempts.pop(username, None)
        return recent

    def _is_locked_out(self, username: str) -> bool:
        """
        [F8] Sliding-window lockout per account.

        Keyed on username alone, which lets an attacker lock a known account out
        on purpose. Production should key on (username, source IP) and pair this
        with a global limit; both need request context this class does not have.
        """
        return len(self._recent_failures(username)) >= MAX_FAILED_ATTEMPTS

    def _record_failure(self, username: str) -> None:
        self._failed_attempts.setdefault(username, []).append(self._now())
