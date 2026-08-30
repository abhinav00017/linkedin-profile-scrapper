import sqlite3

import pytest

from app.store.keys import KeyStore

LI_AT = "AQEDATESTCOOKIEVALUE0123456789abcdefghij"
JSESSIONID = "ajax:1234567890123456789"


@pytest.fixture
def store(tmp_path):
    return KeyStore(db_path=tmp_path / "keys.db", encryption_key=KeyStore.generate_encryption_key())


def test_minting_returns_a_prefixed_key(store):
    key = store.mint(li_at=LI_AT, jsessionid=JSESSIONID, member_name="Jane Doe")
    assert key.startswith("tk_")
    assert len(key) > 30


def test_two_keys_are_never_the_same(store):
    a = store.mint(li_at=LI_AT, jsessionid=JSESSIONID)
    b = store.mint(li_at=LI_AT, jsessionid=JSESSIONID)
    assert a != b


def test_lookup_returns_the_session_that_was_stored(store):
    key = store.mint(li_at=LI_AT, jsessionid=JSESSIONID, member_name="Jane Doe")
    session = store.lookup(key)
    assert session.li_at == LI_AT
    assert session.jsessionid == JSESSIONID
    assert session.member_name == "Jane Doe"


def test_lookup_of_an_unknown_key_returns_nothing(store):
    assert store.lookup("tk_nosuchkey") is None


def test_lookup_of_a_revoked_key_returns_nothing(store):
    key = store.mint(li_at=LI_AT, jsessionid=JSESSIONID)
    store.revoke(key)
    assert store.lookup(key) is None


def test_the_plaintext_key_is_never_written_to_the_database(store, tmp_path):
    key = store.mint(li_at=LI_AT, jsessionid=JSESSIONID)
    raw = (tmp_path / "keys.db").read_bytes()
    assert key.encode() not in raw


def test_the_cookie_is_encrypted_at_rest(store, tmp_path):
    store.mint(li_at=LI_AT, jsessionid=JSESSIONID)
    raw = (tmp_path / "keys.db").read_bytes()
    assert LI_AT.encode() not in raw


def test_a_database_stolen_without_the_encryption_key_yields_nothing(store, tmp_path):
    key = store.mint(li_at=LI_AT, jsessionid=JSESSIONID)
    thief = KeyStore(db_path=tmp_path / "keys.db",
                     encryption_key=KeyStore.generate_encryption_key())
    assert thief.lookup(key) is None


def test_usage_is_counted(store):
    key = store.mint(li_at=LI_AT, jsessionid=JSESSIONID)
    store.lookup(key)
    store.lookup(key)
    assert store.usage(key).request_count == 2


def test_the_bootstrap_key_works_without_any_database_row(tmp_path):
    store = KeyStore(
        db_path=tmp_path / "keys.db",
        encryption_key=KeyStore.generate_encryption_key(),
        bootstrap_key="tk_bootstrap_demo",
        bootstrap_li_at=LI_AT,
        bootstrap_jsessionid=JSESSIONID,
    )
    session = store.lookup("tk_bootstrap_demo")
    assert session.li_at == LI_AT
    assert session.is_bootstrap is True


def test_without_a_bootstrap_configured_that_key_means_nothing(store):
    assert store.lookup("tk_bootstrap_demo") is None


def test_the_store_creates_its_own_schema(tmp_path):
    path = tmp_path / "nested" / "keys.db"
    KeyStore(db_path=path, encryption_key=KeyStore.generate_encryption_key())
    tables = sqlite3.connect(path).execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    assert ("api_keys",) in tables
