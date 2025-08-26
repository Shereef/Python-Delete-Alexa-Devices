"""
Unit tests for utils.py.

Covers: rate_limited decorator, run_with_progress_bar, and print_table.
"""

import time
from alexa_manager.utils import rate_limited


def test_rate_limited_decorator(monkeypatch):
    """
    Test that rate_limited decorator delays function execution when SHOULD_SLEEP is True.

    This test patches the config module and time.sleep, then reloads the utils module
    to ensure the decorator reads the patched value at runtime. This approach ensures
    the decorator's behavior is tested as it would be in production.
    """
    import sys
    import alexa_manager.config as config_module

    monkeypatch.setattr(config_module, "SHOULD_SLEEP", True)
    sys.modules.pop("alexa_manager.utils", None)
    import alexa_manager.utils as utils_module

    sleep_called = {}

    def mock_sleep(seconds):
        sleep_called["slept"] = seconds

    monkeypatch.setattr(time, "sleep", mock_sleep)

    @utils_module.rate_limited
    def increment_value(input_value: int) -> int:
        return input_value + 1

    result = increment_value(1)
    assert result == 2
    assert sleep_called["slept"] == 0.2


def test_rate_limited_no_sleep(monkeypatch):
    """
    Test that rate_limited decorator does not delay when SHOULD_SLEEP is False.
    """
    monkeypatch.setattr("alexa_manager.config.SHOULD_SLEEP", False)

    @rate_limited
    def foo(x):
        return x * 2

    result = foo(3)
    assert result == 6


def test_rate_limited_exception_propagation(monkeypatch):
    """
    Test that exceptions raised in the decorated function propagate correctly.
    """
    monkeypatch.setattr("alexa_manager.config.SHOULD_SLEEP", True)

    @rate_limited
    def foo(x):
        raise ValueError("Test error")

    try:
        foo(1)
    except ValueError as e:
        assert str(e) == "Test error"
    else:
        assert False, "Exception did not propagate"


def test_rate_limited_multiple_calls(monkeypatch):
    """
    Test that rate_limited decorator applies sleep for multiple calls.
    """
    import sys
    import time
    import alexa_manager.config as config_module

    monkeypatch.setattr(config_module, "SHOULD_SLEEP", True)
    sys.modules.pop("alexa_manager.utils", None)
    import alexa_manager.utils as utils_module

    sleep_calls = []

    def fake_sleep(secs):
        sleep_calls.append(secs)

    monkeypatch.setattr(time, "sleep", fake_sleep)

    @utils_module.rate_limited
    def foo(x):
        return x

    for i in range(3):
        foo(i)
    assert sleep_calls == [0.2, 0.2, 0.2]


def test_run_with_progress_bar_runs(monkeypatch):
    """
    Test run_with_progress_bar runs per_item_func for all items.
    """
    from alexa_manager.utils import run_with_progress_bar

    items = [1, 2, 3]
    called = []

    def per_item_func(item, collector):
        called.append(item)

    run_with_progress_bar(items, "Test", per_item_func, [])
    assert called == items


def test_run_with_progress_bar_empty(monkeypatch):
    """
    Test run_with_progress_bar with empty items list.
    Should not call per_item_func and should not error.
    """
    from alexa_manager.utils import run_with_progress_bar

    items = []
    called = []

    def per_item_func(item, collector):
        called.append(item)

    run_with_progress_bar(items, "Empty Test", per_item_func, [])
    assert called == []


def test_run_with_progress_bar_large(monkeypatch):
    """
    Test run_with_progress_bar with a large list of items.
    Should process all items without error.
    """
    from alexa_manager.utils import run_with_progress_bar

    items = list(range(1000))
    called = []

    def per_item_func(item, collector):
        called.append(item)

    run_with_progress_bar(items, "Large Test", per_item_func, [])
    assert called == items


def test_run_with_progress_bar_exception(monkeypatch, caplog):
    """
    Test run_with_progress_bar when per_item_func raises an exception.
    Should log the error and collect the failed item, not propagate the exception.
    """
    from alexa_manager.utils import run_with_progress_bar

    items = [1, 2, 3]
    failed = []

    def per_item_func(item, collector):
        if item == 2:
            raise RuntimeError("fail")

    with caplog.at_level("ERROR"):
        run_with_progress_bar(items, "Exception Test", per_item_func, failed)

    assert failed == [2]
    assert any("Unexpected error processing item '2'" in m for m in caplog.messages)


def test_run_with_progress_bar_handles_exceptions(monkeypatch, caplog):
    """
    Test that run_with_progress_bar collects items that raise unexpected exceptions
    and logs the error message.
    """
    from alexa_manager.utils import run_with_progress_bar

    items = ["ok", "fail", "ok2"]
    called = []
    failed = []

    def per_item_func(item, collector):
        if item == "fail":
            raise RuntimeError("Unexpected failure!")
        called.append(item)

    with caplog.at_level("ERROR"):
        run_with_progress_bar(items, "Test Exception Handling", per_item_func, failed)

    assert called == ["ok", "ok2"]
    assert failed == ["fail"]
    assert any("Unexpected error processing item 'fail'" in m for m in caplog.messages)


def test_print_table_runs():
    """
    Test print_table runs without error for simple data.
    """
    from alexa_manager.utils import print_table

    data = [{"A": 1, "B": 2}, {"A": 3, "B": 4}]
    print_table(data, ["A", "B"], "Test Table")


def test_print_table_empty():
    """
    Test print_table with empty data and columns.
    Should not raise an error.
    """
    from alexa_manager.utils import print_table

    print_table([], [], "Empty Table")


def test_print_table_missing_columns():
    """
    Test print_table with missing columns in data.
    Should not raise an error and should handle gracefully.
    """
    from alexa_manager.utils import print_table

    data = [{"A": 1}, {"B": 2}]
    print_table(data, ["A", "B", "C"], "Missing Columns Table")


def test_print_table_non_dict_data():
    """
    Test print_table with non-dict data (should handle gracefully).
    """
    from alexa_manager.utils import print_table

    data = [1, 2, 3]
    try:
        print_table(data, ["A"], "Non-Dict Table")
    except Exception:
        assert False, "print_table should not raise error for non-dict data"


def test_print_table_large():
    """
    Test print_table with a very large table.
    Should not raise an error.
    """
    from alexa_manager.utils import print_table

    data = [{"A": i, "B": i * 2} for i in range(1000)]
    print_table(data, ["A", "B"], "Large Table")


def test_print_table_missing_headers():
    """
    Test print_table with headers not present in any data row.
    Should not raise an error.
    """
    from alexa_manager.utils import print_table

    data = [{"A": 1}, {"A": 2}]
    print_table(data, ["X", "Y"], "Missing Headers Table")


def test_convert_normalised_area_to_alexa_name_basic():
    """
    Test convert_normalised_area_to_alexa_name with a standard string containing underscores.
    """
    from alexa_manager.utils import convert_normalised_area_to_alexa_name

    assert convert_normalised_area_to_alexa_name("living_room") == "Living Room"
    assert convert_normalised_area_to_alexa_name("bedroom_2") == "Bedroom 2"


def test_convert_normalised_area_to_alexa_name_empty():
    """
    Test convert_normalised_area_to_alexa_name with an empty string.
    """
    from alexa_manager.utils import convert_normalised_area_to_alexa_name

    assert convert_normalised_area_to_alexa_name("") == ""


def test_convert_normalised_area_to_alexa_name_multiple_underscores():
    """
    Test convert_normalised_area_to_alexa_name with multiple underscores and leading/trailing spaces.
    """
    from alexa_manager.utils import convert_normalised_area_to_alexa_name

    assert convert_normalised_area_to_alexa_name("_garage__door_") == "Garage  Door"


def test_convert_normalised_area_to_alexa_name_type_error():
    """
    Test convert_normalised_area_to_alexa_name raises TypeError for non-string input.
    """
    from alexa_manager.utils import convert_normalised_area_to_alexa_name
    import pytest

    with pytest.raises(TypeError):
        convert_normalised_area_to_alexa_name(None)
    with pytest.raises(TypeError):
        convert_normalised_area_to_alexa_name(123)


def test_normalise_area_name_basic():
    """
    Test normalise_area_name with typical input.
    """
    from alexa_manager.utils import normalise_area_name

    assert normalise_area_name("Living Room") == "living_room"
    assert normalise_area_name("  Kitchen  ") == "kitchen"


def test_normalise_area_name_empty():
    """
    Test normalise_area_name with empty string.
    """
    from alexa_manager.utils import normalise_area_name

    assert normalise_area_name("") == ""


def test_normalise_area_name_multiple_underscores():
    """
    Test normalise_area_name with multiple underscores.
    """
    from alexa_manager.utils import normalise_area_name

    assert normalise_area_name(" garage  door ") == "garage__door"


def test_sanitize_list_basic():
    """
    Test sanitize_list with mixed types and dicts with key.
    """
    from alexa_manager.utils import sanitize_list

    input_list = ["a", 1, {"name": "foo"}, {"other": "bar"}]
    result = sanitize_list(input_list, key="name")
    assert result == ["a", "1", "foo", "{'other': 'bar'}"]


def test_sanitize_list_no_key():
    """
    Test sanitize_list with dicts and no key provided.
    """
    from alexa_manager.utils import sanitize_list

    input_list = [{"x": 1}, "y"]
    result = sanitize_list(input_list)
    assert result == ["{'x': 1}", "y"]


def test_sanitize_list_empty():
    """
    Test sanitize_list with empty list.
    """
    from alexa_manager.utils import sanitize_list

    assert sanitize_list([]) == []


def test_flatten_dict_basic():
    """
    Test flatten_dict with nested dicts and lists.
    """
    from alexa_manager.utils import flatten_dict

    d = {"a": {"b": 2}, "c": [1, {"d": 3}]}
    result = flatten_dict(d)
    assert result["a"] == "{'b': 2}"
    assert result["c"][1] == "{'d': 3}"


def test_flatten_dict_non_dict():
    """
    Test flatten_dict with non-dict input.
    """
    from alexa_manager.utils import flatten_dict

    assert flatten_dict(123) == 123
    assert flatten_dict("abc") == "abc"


def test_format_appliance_id_for_api_basic():
    """
    Test format_appliance_id_for_api with valid string.
    """
    from alexa_manager.utils import format_appliance_id_for_api
    import json

    appliance_id = "device123"
    result = format_appliance_id_for_api(appliance_id)
    assert json.loads(result) == {"applianceId": "device123"}


def test_format_appliance_id_for_api_invalid():
    """
    Test format_appliance_id_for_api raises ValueError for invalid input.
    """
    from alexa_manager.utils import format_appliance_id_for_api
    import pytest

    with pytest.raises(ValueError):
        format_appliance_id_for_api("")
    with pytest.raises(ValueError):
        format_appliance_id_for_api(None)
    with pytest.raises(ValueError):
        format_appliance_id_for_api(123)


def test_dry_run_action_basic(monkeypatch):
    """
    Test dry_run_action prints expected message (fallback if rich not installed).
    Forces fallback by removing 'rich' from sys.modules.
    Handles trailing spaces and output variations.
    Ensures print output is captured regardless of arguments.
    """
    import sys
    from alexa_manager import utils

    output = []
    monkeypatch.setattr(
        "builtins.print",
        lambda *args, **kwargs: output.append(" ".join(str(a) for a in args)),
    )
    sys.modules["rich"] = None
    sys.modules["rich.console"] = None
    utils.dry_run_action("DELETE", "Device1", "http://api", "extra-info")
    assert any(
        "Would DELETE Device1 at http://api" in msg and "extra-info" in msg
        for msg in output
    ), f"Output was: {output}"
    # Clean up monkeypatch
    sys.modules.pop("rich", None)
    sys.modules.pop("rich.console", None)


def test_dry_run_action_rich(monkeypatch):
    """
    Test dry_run_action uses rich if available (mock Console.print).
    """
    from alexa_manager import utils

    class MockConsole:
        def print(self, msg):
            utils._dry_run_msg = msg

    monkeypatch.setattr("rich.console.Console", lambda: MockConsole())
    utils.dry_run_action("CREATE", "Group1", "http://api")
    assert "Would CREATE Group1 at [green]http://api[/green]" in utils._dry_run_msg
