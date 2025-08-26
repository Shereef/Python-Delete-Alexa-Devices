"""
Unit tests for config.py.

Covers: reading TOML, ensuring user config, merging configs, and error handling.
"""

import tomllib
import pytest
from alexa_manager.config import (
    load_config,
    read_toml_file,
    ensure_user_config_exists,
)


def test_read_toml_file_valid(tmp_path):
    """
    Test reading a valid TOML file returns the correct dictionary.
    """
    file = tmp_path / "test.toml"
    file.write_text('foo = "bar"\n')
    result = read_toml_file(str(file))
    assert result == {"foo": "bar"}


def test_read_toml_file_invalid(tmp_path):
    """
    Test reading an invalid TOML file raises TOMLDecodeError.
    """
    file = tmp_path / "bad.toml"
    file.write_text("bad toml")
    with pytest.raises(tomllib.TOMLDecodeError):
        read_toml_file(str(file))


def test_read_toml_file_malformed(tmp_path):
    """
    Test reading a malformed TOML file raises TOMLDecodeError.
    """
    file = tmp_path / "malformed.toml"
    file.write_text('foo = "bar"\n[invalid')
    with pytest.raises(tomllib.TOMLDecodeError):
        read_toml_file(str(file))


def test_read_toml_file_empty(tmp_path):
    """
    Test reading an empty TOML file returns an empty dictionary.
    """
    file = tmp_path / "empty.toml"
    file.write_text("")
    result = read_toml_file(str(file))
    assert result == {}


def test_read_toml_file_nested(tmp_path):
    """
    Test reading a TOML file with nested structures.
    """
    file = tmp_path / "nested.toml"
    file.write_text('[section]\nfoo = "bar"\n')
    result = read_toml_file(str(file))
    assert "section" in result
    assert result["section"]["foo"] == "bar"


def test_ensure_user_config_exists_toml(tmp_path):
    """
    Test that user config is created if it does not exist (TOML).
    """
    global_path = tmp_path / "global.toml"
    user_path = tmp_path / "user.toml"
    global_path.write_text("foo = 1\n")
    ensure_user_config_exists(str(global_path), str(user_path))
    assert user_path.exists()
    assert user_path.read_text() == "foo = 1\n"


def test_ensure_user_config_exists(tmp_path):
    """
    Test ensure_user_config_exists copies global config to user config if missing.
    """
    global_path = tmp_path / "global.toml"
    user_path = tmp_path / "user.toml"
    global_path.write_text('foo = "bar"')
    # User config does not exist
    ensure_user_config_exists(str(global_path), str(user_path))
    assert user_path.exists()
    assert user_path.read_text() == 'foo = "bar"'


def test_load_config_merges_toml(monkeypatch, tmp_path):
    """
    Test that load_config merges global and user TOML config, with user config taking precedence.
    """
    global_path = tmp_path / "global.toml"
    user_path = tmp_path / "user.toml"
    global_path.write_text("foo = 1\nbar = 2\nCOOKIE = 'dummy_cookie'\n")
    user_path.write_text("bar = 3\nbaz = 4\nCOOKIE = 'dummy_cookie'\n")
    monkeypatch.chdir(tmp_path)
    config = load_config(str(global_path), str(user_path))
    assert config["foo"] == 1
    assert config["bar"] == 3
    assert config["baz"] == 4


def test_load_config_missing_files(tmp_path):
    """
    Test load_config handles missing config files gracefully (should exit).
    """
    global_path = tmp_path / "missing_global.toml"
    user_path = tmp_path / "missing_user.toml"
    with pytest.raises(SystemExit):
        load_config(str(global_path), str(user_path))


def test_load_config_missing_required_fields(tmp_path):
    """
    Test load_config with missing required fields triggers validation error and exits.
    """
    global_path = tmp_path / "global.toml"
    user_path = tmp_path / "user.toml"
    # Only provide a non-required field
    global_path.write_text("DEBUG = true")
    user_path.write_text("")
    with pytest.raises(SystemExit):
        load_config(str(global_path), str(user_path))


def test_load_config_large_files(tmp_path):
    """
    Test load_config handles very large config files.
    """
    global_path = tmp_path / "large_global.toml"
    user_path = tmp_path / "large_user.toml"
    global_content = (
        "\n".join([f"key{i} = {i}" for i in range(1000)])
        + "\nCOOKIE = 'dummy_cookie'\n"
    )
    user_content = (
        "\n".join([f"key{i} = {i + 1000}" for i in range(1000)])
        + "\nCOOKIE = 'dummy_cookie'\n"
    )
    global_path.write_text(global_content)
    user_path.write_text(user_content)
    config = load_config(str(global_path), str(user_path))
    assert config["key999"] == 1999


def test_load_config_invalid_types(tmp_path):
    """
    Test load_config handles invalid data types in config files.
    """
    global_path = tmp_path / "invalid_types.toml"
    user_path = tmp_path / "user.toml"
    global_path.write_text(
        'foo = [1, 2, 3]\nbar = {baz = "qux"}\nCOOKIE = "dummy_cookie"'
    )
    user_path.write_text('bar = "override"\nCOOKIE = "dummy_cookie"')
    config = load_config(str(global_path), str(user_path))
    assert isinstance(config["foo"], list)
    assert config["bar"] == "override"
