import os

import pytest

from app import config
import importlib


def test_load_env_file_sets_new_vars_and_keeps_existing(tmp_path, monkeypatch):
    env_path = tmp_path / "sample.env"
    env_path.write_text(
        "\n".join(
            [
                "# comment",
                "EXISTING=from_file",
                "NEW_VAR=new_value",
                "EMPTY=",
                "INVALID_LINE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("EXISTING", "from_env")
    monkeypatch.delenv("NEW_VAR", raising=False)

    config._load_env_file(env_path)

    assert os.environ["EXISTING"] == "from_env"
    assert os.environ["NEW_VAR"] == "new_value"


def test_load_env_file_returns_when_path_missing(tmp_path):
    missing_path = tmp_path / "missing.env"
    config._load_env_file(missing_path)


@pytest.mark.parametrize(
    "value, expected_message",
    [
        ("0", "TEST_POSITIVE_INT must be > 0"),
        ("-1", "TEST_POSITIVE_INT must be > 0"),
        ("oops", "TEST_POSITIVE_INT must be an integer"),
    ],
)
def test_get_positive_int_rejects_invalid_values(monkeypatch, value, expected_message):
    monkeypatch.setenv("TEST_POSITIVE_INT", value)
    with pytest.raises(ValueError, match=expected_message):
        config._get_positive_int("TEST_POSITIVE_INT", 7)


def test_get_positive_int_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("TEST_POSITIVE_INT", raising=False)
    assert config._get_positive_int("TEST_POSITIVE_INT", 7) == 7


def test_get_positive_int_returns_env_value(monkeypatch):
    monkeypatch.setenv("TEST_POSITIVE_INT", "5")
    assert config._get_positive_int("TEST_POSITIVE_INT", 7) == 5


def test_topone_timeout_seconds_rejects_less_than_600(monkeypatch):
    monkeypatch.setenv("TOPONE_TIMEOUT_SECONDS", "599.9")
    with pytest.raises(ValueError, match="TOPONE_TIMEOUT_SECONDS must be >= 600"):
        importlib.reload(config)
    monkeypatch.delenv("TOPONE_TIMEOUT_SECONDS", raising=False)
    importlib.reload(config)


def test_topone_timeout_seconds_accepts_minimum(monkeypatch):
    monkeypatch.setenv("TOPONE_TIMEOUT_SECONDS", "600")
    reloaded = importlib.reload(config)
    assert reloaded.TOPONE_TIMEOUT_SECONDS == 600.0
    monkeypatch.delenv("TOPONE_TIMEOUT_SECONDS", raising=False)
    importlib.reload(config)


def test_scene_min_count_exceeds_max_raises(monkeypatch):
    monkeypatch.setenv("SCENE_MIN_COUNT", "10")
    monkeypatch.setenv("SCENE_MAX_COUNT", "5")
    with pytest.raises(ValueError, match="SCENE_MIN_COUNT must be <= SCENE_MAX_COUNT"):
        importlib.reload(config)
    monkeypatch.delenv("SCENE_MIN_COUNT", raising=False)
    monkeypatch.delenv("SCENE_MAX_COUNT", raising=False)
    importlib.reload(config)


def test_require_memgraph_host_missing(monkeypatch):
    monkeypatch.delenv("MEMGRAPH_HOST", raising=False)
    with pytest.raises(RuntimeError, match="MEMGRAPH_HOST"):
        config.require_memgraph_host()


def test_require_memgraph_port_missing(monkeypatch):
    monkeypatch.delenv("MEMGRAPH_PORT", raising=False)
    with pytest.raises(RuntimeError, match="MEMGRAPH_PORT"):
        config.require_memgraph_port()


def test_require_memgraph_port_invalid(monkeypatch):
    monkeypatch.setenv("MEMGRAPH_PORT", "oops")
    with pytest.raises(ValueError, match="MEMGRAPH_PORT must be an integer"):
        config.require_memgraph_port()


def test_require_memgraph_port_valid(monkeypatch):
    monkeypatch.setenv("MEMGRAPH_PORT", "7687")
    assert config.require_memgraph_port() == 7687


def test_require_memgraph_port_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("MEMGRAPH_PORT", "0")
    with pytest.raises(ValueError, match="MEMGRAPH_PORT must be > 0"):
        config.require_memgraph_port()
