"""API keys and the LinkedIn sessions behind them.

We store a hash of the key, never the key. We encrypt the cookie, so a stolen
database file is not a set of working LinkedIn sessions.
"""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    key_hash         TEXT PRIMARY KEY,
    li_at_encrypted  BLOB NOT NULL,
    jsessionid       TEXT,
    member_name      TEXT,
    member_public_id TEXT,
    created_at       TEXT NOT NULL,
    last_used_at     TEXT,
    request_count    INTEGER NOT NULL DEFAULT 0,
    revoked          INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass(frozen=True)
class Session:
    li_at: str
    jsessionid: str | None
    member_name: str | None = None
    member_public_id: str | None = None
    is_bootstrap: bool = False


@dataclass(frozen=True)
class Usage:
    request_count: int
    created_at: str | None
    last_used_at: str | None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KeyStore:
    def __init__(
        self,
        db_path: Path | str,
        encryption_key: str | bytes,
        bootstrap_key: str | None = None,
        bootstrap_li_at: str | None = None,
        bootstrap_jsessionid: str | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(encryption_key)
        self._bootstrap_key = bootstrap_key
        self._bootstrap_li_at = bootstrap_li_at
        self._bootstrap_jsessionid = bootstrap_jsessionid
        with self._connect() as db:
            db.executescript(SCHEMA)

    @staticmethod
    def generate_encryption_key() -> str:
        return Fernet.generate_key().decode()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def mint(
        self,
        li_at: str,
        jsessionid: str | None = None,
        member_name: str | None = None,
        member_public_id: str | None = None,
    ) -> str:
        key = f"tk_{secrets.token_urlsafe(32)}"
        with self._connect() as db:
            db.execute(
                "INSERT INTO api_keys (key_hash, li_at_encrypted, jsessionid, "
                "member_name, member_public_id, created_at) VALUES (?,?,?,?,?,?)",
                (
                    self._hash(key),
                    self._fernet.encrypt(li_at.encode()),
                    jsessionid,
                    member_name,
                    member_public_id,
                    _now(),
                ),
            )
        return key

    def lookup(self, key: str) -> Session | None:
        """Return the session for a key, counting the use. None if unusable."""
        if self._bootstrap_key and secrets.compare_digest(key, self._bootstrap_key):
            if not self._bootstrap_li_at:
                return None
            return Session(
                li_at=self._bootstrap_li_at,
                jsessionid=self._bootstrap_jsessionid,
                member_name="bootstrap",
                is_bootstrap=True,
            )

        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0",
                (self._hash(key),),
            ).fetchone()
            if row is None:
                return None

            try:
                li_at = self._fernet.decrypt(row["li_at_encrypted"]).decode()
            except InvalidToken:
                # Wrong encryption key for this database. Refuse rather than guess.
                return None

            db.execute(
                "UPDATE api_keys SET last_used_at = ?, request_count = request_count + 1 "
                "WHERE key_hash = ?",
                (_now(), row["key_hash"]),
            )

        return Session(
            li_at=li_at,
            jsessionid=row["jsessionid"],
            member_name=row["member_name"],
            member_public_id=row["member_public_id"],
        )

    def revoke(self, key: str) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE api_keys SET revoked = 1 WHERE key_hash = ?", (self._hash(key),)
            )

    def usage(self, key: str) -> Usage | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT request_count, created_at, last_used_at FROM api_keys "
                "WHERE key_hash = ?",
                (self._hash(key),),
            ).fetchone()
        if row is None:
            return None
        return Usage(
            request_count=row["request_count"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )
