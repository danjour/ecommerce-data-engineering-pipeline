import pytest
from config import required_env, int_env

def test_required_env_ok(monkeypatch):
    monkeypatch.setenv("X_TEST", "ok")
    assert required_env("X_TEST") == "ok"

def test_required_env_missing(monkeypatch):
    monkeypatch.delenv("X_TEST", raising=False)
    with pytest.raises(ValueError):
        required_env("X_TEST")

def test_int_env_default(monkeypatch):
    monkeypatch.delenv("X_INT", raising=False)
    assert int_env("X_INT", 8) == 8

def test_int_env_invalid(monkeypatch):
    monkeypatch.setenv("X_INT", "abc")
    with pytest.raises(ValueError):
        int_env("X_INT", 8)