"""
test_api.py

Unit tests for Alexa Media Player command functions in api.py.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests
import tenacity
from alexa_manager import api
from alexa_manager.api import (
    get_entities,
    update_alexa_group,
    find_group_by_id,
    put_alexa_group,
    update_alexa_groups_batch,
    sync_ha_alexa_groups,
    find_missing_ha_groups,
    create_alexa_group_for_ha_area,
    sync_alexa_group_entities,
)
from alexa_manager.models import AlexaEntities


# Test: send_alexa_command_via_ha_service success
@patch("alexa_manager.api.requests.post")
def test_send_alexa_command_success(mock_post):
    """
    Test that send_alexa_command_via_ha_service returns device/entity ID on status 200.
    All network calls are mocked to prevent real HTTP requests.
    """
    mock_post.return_value.status_code = 200
    # Simulate device_id used
    with (
        patch("alexa_manager.api.ALEXA_DEVICE_ID", "device123"),
        patch("alexa_manager.api.ALEXA_ENTITY_ID", ""),
    ):
        result = api.send_alexa_command_via_ha_service("discover devices")
        assert result == "device123"
    # Simulate entity_id used
    with (
        patch("alexa_manager.api.ALEXA_DEVICE_ID", ""),
        patch("alexa_manager.api.ALEXA_ENTITY_ID", "entity456"),
    ):
        result = api.send_alexa_command_via_ha_service("discover devices")
        assert result == "entity456"


# Test: send_alexa_command_via_ha_service failure
@patch("alexa_manager.api.requests.post")
@patch("alexa_manager.api.fetch_last_used_alexa", return_value="media_player.test_echo")
def test_send_alexa_command_failure(mock_fetch_last_used, mock_post):
    """
    Test that send_alexa_command_via_ha_service raises RetryError on non-200 status.
    All network calls are mocked to prevent real HTTP requests.
    """
    mock_post.return_value.status_code = 500
    with pytest.raises(tenacity.RetryError) as exc_info:
        api.send_alexa_command_via_ha_service("discover devices")
    # Optionally check the cause is HTTPError
    assert isinstance(exc_info.value.last_attempt.exception(), requests.HTTPError)


# Test: send_alexa_command_via_ha_service missing config
@patch("alexa_manager.api.requests.post")
def test_send_alexa_command_missing_config(mock_post):
    """
    Test that send_alexa_command_via_ha_service raises ValueError if config is missing.
    All network calls are mocked to prevent real HTTP requests.
    """
    # Patch config values directly using monkeypatch pattern
    with (
        patch("alexa_manager.api.ALEXA_DEVICE_ID", ""),
        patch("alexa_manager.api.ALEXA_ENTITY_ID", ""),
        patch("alexa_manager.api.fetch_last_used_alexa", return_value=""),
    ):
        with pytest.raises(ValueError):
            api.send_alexa_command_via_ha_service("discover devices")


# Test: alexa_discover_devices delegates to send_alexa_command_via_ha_service
@patch("alexa_manager.api.requests.post")
@patch("alexa_manager.api.send_alexa_command_via_ha_service")
def test_alexa_discover_devices_delegation(mock_send, mock_post):
    """
    Test that alexa_discover_devices calls send_alexa_command_via_ha_service with correct command and returns the ID.
    All network calls are mocked to prevent real HTTP requests.
    """
    mock_send.return_value = "entity789"
    result = api.alexa_discover_devices()
    assert result == "entity789"
    mock_send.assert_called_once_with("discover devices")


@patch("alexa_manager.api.requests.post")
def test_get_ha_areas_success(mock_post):
    """
    Test get_ha_areas returns parsed area dict on valid response.
    """
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = '{"Living Room":["light.lamp1","switch.tv"]}'
    result = api.get_ha_areas()
    assert result == {"Living Room": ["light.lamp1", "switch.tv"]}


@patch("alexa_manager.api.requests.post")
def test_get_ha_areas_invalid_json(mock_post):
    """
    Test get_ha_areas returns empty dict on invalid JSON response.
    """
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "not a json"
    result = api.get_ha_areas()
    assert result == {}


@patch("alexa_manager.api.requests.post")
def test_get_ha_areas_api_error(mock_post):
    """
    Test get_ha_areas returns empty dict on API error.
    """
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "Internal Server Error"
    result = api.get_ha_areas()
    assert result == {}


@patch("alexa_manager.api.requests.post")
def test_fetch_last_used_alexa_success(mock_post):
    """
    Test fetch_last_used_alexa returns entity_id string on valid response.
    """
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = '"media_player.kitchen_echo"'
    result = api.fetch_last_used_alexa()
    assert result == "media_player.kitchen_echo"


@patch("alexa_manager.api.requests.post")
def test_fetch_last_used_alexa_empty(mock_post):
    """
    Test fetch_last_used_alexa returns empty string if no device found.
    """
    mock_post.return_value.status_code = 200
    mock_post.return_value.text = '""'
    result = api.fetch_last_used_alexa()
    assert result == ""


@patch("alexa_manager.api.requests.post")
def test_fetch_last_used_alexa_api_error(mock_post):
    """
    Test fetch_last_used_alexa returns empty string on API error.
    """
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "Internal Server Error"
    result = api.fetch_last_used_alexa()
    assert result == ""


@patch("alexa_manager.api.get_entities")
@patch("alexa_manager.api.alexa_discover_devices")
def test_wait_for_device_discovery_success(mock_discover, mock_get_entities):
    """
    Test wait_for_device_discovery returns True when new devices are discovered and
    the entity count remains stable for the required consecutive polls.
    """
    # Simulate: 2, 2, 3, 3, 3 (stable_required=3 by default)
    mock_get_entities.side_effect = [
        MagicMock(entities=[1, 2]),  # initial
        MagicMock(entities=[1, 2]),  # poll 1
        MagicMock(entities=[1, 2, 3]),  # poll 2 (increase)
        MagicMock(entities=[1, 2, 3]),  # poll 3 (stable 1)
        MagicMock(entities=[1, 2, 3]),  # poll 4 (stable 2)
        MagicMock(entities=[1, 2, 3]),  # poll 5 (stable 3)
    ]
    mock_discover.return_value = None
    result = api.wait_for_device_discovery(timeout=10, poll_interval=0.01)
    assert result is True


@patch("alexa_manager.api.get_entities")
@patch("alexa_manager.api.alexa_discover_devices")
def test_wait_for_device_discovery_timeout(mock_discover, mock_get_entities):
    """
    Test wait_for_device_discovery returns False if no new devices are discovered before timeout.
    """
    # Always returns 2 entities
    mock_get_entities.return_value = MagicMock(__len__=lambda s: 2)
    mock_discover.return_value = None
    result = api.wait_for_device_discovery(timeout=0.05, poll_interval=0.01)
    assert result is False


@patch("alexa_manager.api.get_entities", side_effect=Exception("fetch error"))
@patch("alexa_manager.api.alexa_discover_devices")
def test_wait_for_device_discovery_initial_fetch_error(
    mock_discover, mock_get_entities
):
    """
    Test wait_for_device_discovery returns False if initial entity fetch fails.
    """
    result = api.wait_for_device_discovery(timeout=1, poll_interval=0.01)
    assert result is False


@patch("alexa_manager.api.get_entities")
@patch(
    "alexa_manager.api.alexa_discover_devices", side_effect=Exception("discover error")
)
def test_wait_for_device_discovery_discover_error(mock_discover, mock_get_entities):
    """
    Test wait_for_device_discovery returns False if discovery trigger fails.
    """
    mock_get_entities.return_value = MagicMock(__len__=lambda s: 2)
    result = api.wait_for_device_discovery(timeout=1, poll_interval=0.01)
    assert result is False


def test_get_entities_empty(monkeypatch):
    """
    Test get_entities returns empty AlexaEntities on empty response.
    """

    class MockEmptyResponse:
        text = ""

        def json(self):
            return []

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockEmptyResponse())
    entities_result = get_entities()
    assert isinstance(entities_result, AlexaEntities)
    assert entities_result.entities == []


def test_get_entities_malformed_json(monkeypatch):
    """
    Test get_entities handles malformed JSON gracefully.
    """

    class MockMalformedResponse:
        text = "bad json"

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockMalformedResponse())
    entities_result = get_entities()
    assert isinstance(entities_result, AlexaEntities)
    assert entities_result.entities == []


def test_update_alexa_group_success(monkeypatch):
    """
    Test update_alexa_group returns True on successful PUT.
    """
    groups = [
        {
            "id": "group123",
            "entityId": "entity123",
            "name": "Test Group",
            "entityType": "GROUP",
            "groupType": "APPLIANCE",
            "childIds": ["child1", "child2"],
            "defaults": [],
            "associatedUnitIds": [],
            "defaultMetadataByType": {},
            "implicitTargetingByType": {},
            "applianceIds": [],
        }
    ]
    updated_fields = {"name": "Updated Group"}

    class FakeResponse:
        status_code = 200
        text = "OK"

    monkeypatch.setattr("requests.put", lambda *a, **k: FakeResponse())
    result = update_alexa_group("group123", updated_fields, groups)
    assert result is True


def test_update_alexa_group_not_found():
    """
    Test update_alexa_group raises ValueError if group not found.
    """
    groups = [{"id": "group123", "name": "Test Group"}]
    updated_fields = {"name": "Updated Group"}
    with pytest.raises(ValueError):
        update_alexa_group("missing_id", updated_fields, groups)


def test_update_alexa_group_failure(monkeypatch):
    """
    Test update_alexa_group returns False on failed PUT.
    """
    groups = [{"id": "group123", "name": "Test Group"}]
    updated_fields = {"name": "Updated Group"}

    class FakeResponse:
        status_code = 400
        text = "Bad Request"

    monkeypatch.setattr("requests.put", lambda *a, **k: FakeResponse())
    result = update_alexa_group("group123", updated_fields, groups)
    assert result is False


def test_update_alexa_group_exception(monkeypatch):
    """
    Test update_alexa_group returns False on request exception.
    """
    groups = [{"id": "group123", "name": "Test Group"}]
    updated_fields = {"name": "Updated Group"}

    def raise_exc(*a, **k):
        raise Exception("Network error")

    monkeypatch.setattr("requests.put", raise_exc)
    result = update_alexa_group("group123", updated_fields, groups)
    assert result is False


def test_find_group_by_id_found():
    """
    Test find_group_by_id returns the correct group when found.
    """
    groups = [
        {"id": "group1", "name": "Group 1"},
        {"id": "group2", "name": "Group 2"},
    ]
    result = find_group_by_id(groups, "group2")
    assert result["name"] == "Group 2"


def test_find_group_by_id_not_found():
    """
    Test find_group_by_id raises ValueError when group is not found.
    """
    groups = [{"id": "group1", "name": "Group 1"}]
    with pytest.raises(ValueError):
        find_group_by_id(groups, "missing")


def test_put_alexa_group_success(monkeypatch):
    """
    Test put_alexa_group returns True on successful PUT.
    """
    group_data = {
        "id": "group123",
        "name": "Test Group",
        "entityId": "entity123",
        "entityType": "GROUP",
        "groupType": "APPLIANCE",
        "childIds": [],
        "defaults": [],
        "associatedUnitIds": [],
        "defaultMetadataByType": {},
        "implicitTargetingByType": {},
        "applianceIds": [],
    }
    updated_fields = {"name": "Updated Group"}

    class FakeResponse:
        status_code = 200
        text = "OK"

    monkeypatch.setattr("requests.put", lambda *a, **k: FakeResponse())
    result = put_alexa_group(group_data, updated_fields)
    assert result is True


def test_put_alexa_group_failure(monkeypatch):
    """
    Test put_alexa_group returns False on failed PUT.
    """
    group_data = {"id": "group123", "name": "Test Group"}
    updated_fields = {"name": "Updated Group"}

    class FakeResponse:
        status_code = 400
        text = "Bad Request"

    monkeypatch.setattr("requests.put", lambda *a, **k: FakeResponse())
    result = put_alexa_group(group_data, updated_fields)
    assert result is False


def test_update_alexa_groups_batch(monkeypatch):
    """
    Test update_alexa_groups_batch processes multiple updates and returns correct results.
    """

    def fake_update_alexa_group(
        group_id, updated_fields, groups, url_base=None, headers=None
    ):
        return group_id != "fail_id"

    monkeypatch.setattr("alexa_manager.api.update_alexa_group", fake_update_alexa_group)
    groups = [
        {"id": "group1", "name": "Group 1"},
        {"id": "fail_id", "name": "Group Fail"},
    ]
    updates = [
        {"group_id": "group1", "updated_fields": {"name": "New Name 1"}},
        {"group_id": "fail_id", "updated_fields": {"name": "Should Fail"}},
    ]
    results = update_alexa_groups_batch(updates, groups)
    assert results["group1"] is True
    assert results["fail_id"] is False


def test_update_alexa_groups_batch_empty():
    """
    Test update_alexa_groups_batch with empty updates and groups lists.
    Should return an empty result dict.
    """
    results = update_alexa_groups_batch([], [])
    assert results == {}


def test_update_alexa_groups_batch_invalid_type():
    """
    Test update_alexa_groups_batch with invalid input types.
    Should raise TypeError or handle gracefully.
    """
    with pytest.raises(TypeError):
        update_alexa_groups_batch(None, None)


def test_update_alexa_groups_batch_exception(monkeypatch):
    """
    Test update_alexa_groups_batch handles exceptions in update_alexa_group.
    Should log error and set result to False for failed group.
    """

    def fake_update_alexa_group(
        group_id, updated_fields, groups, url_base=None, headers=None
    ):
        if group_id == "error_id":
            raise ValueError("Simulated error")
        return True

    monkeypatch.setattr("alexa_manager.api.update_alexa_group", fake_update_alexa_group)
    groups = [{"id": "error_id", "name": "Error Group"}]
    updates = [{"group_id": "error_id", "updated_fields": {"name": "Should Error"}}]
    results = update_alexa_groups_batch(updates, groups)
    assert results["error_id"] is False


def test_update_alexa_groups_batch_large(monkeypatch):
    """
    Test update_alexa_groups_batch with a large number of updates.
    Should process all updates and return correct results.
    """

    def fake_update_alexa_group(
        group_id, updated_fields, groups, url_base=None, headers=None
    ):
        return True

    monkeypatch.setattr("alexa_manager.api.update_alexa_group", fake_update_alexa_group)
    groups = [{"id": f"group{i}", "name": f"Group {i}"} for i in range(100)]
    updates = [
        {"group_id": f"group{i}", "updated_fields": {"name": f"New Name {i}"}}
        for i in range(100)
    ]
    results = update_alexa_groups_batch(updates, groups)
    assert all(results.values())


def test_sync_ha_alexa_groups_create(monkeypatch):
    """
    Test sync_ha_alexa_groups creates missing Alexa groups with correct entities.
    """
    ha_areas = {"Living Room": ["light.lamp"]}
    alexa_groups = []
    ha_to_alexa = {"Living Room": ["appl1"]}

    class FakeResponse:
        status_code = 200
        text = "OK"

    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse())
    result = sync_ha_alexa_groups(
        ha_areas, alexa_groups, ha_to_alexa, mode="update_only"
    )
    assert "Living Room" in result["created"]


def test_sync_ha_alexa_groups_update_only(monkeypatch):
    """
    Test sync_ha_alexa_groups adds missing entities in update_only mode.
    """
    ha_areas = {"Bedroom": ["switch.tv"]}
    alexa_groups = [{"name": "Bedroom", "id": "group1", "applianceIds": ["appl1"]}]
    ha_to_alexa = {"Bedroom": ["appl1", "appl2"]}
    monkeypatch.setattr("alexa_manager.api.update_alexa_group", lambda *a, **k: True)
    result = sync_ha_alexa_groups(
        ha_areas, alexa_groups, ha_to_alexa, mode="update_only"
    )
    assert "Bedroom" in result["updated"]


def test_sync_ha_alexa_groups_full(monkeypatch):
    """
    Test sync_ha_alexa_groups adds/removes entities in full mode.
    """
    ha_areas = {"Kitchen": ["sensor.temp"]}
    alexa_groups = [
        {"name": "Kitchen", "id": "group2", "applianceIds": ["appl1", "appl2"]}
    ]
    ha_to_alexa = {"Kitchen": ["appl3"]}
    monkeypatch.setattr("alexa_manager.api.update_alexa_group", lambda *a, **k: True)
    result = sync_ha_alexa_groups(ha_areas, alexa_groups, ha_to_alexa, mode="full")
    assert "Kitchen" in result["updated"]


def test_sync_ha_alexa_groups_skipped():
    """
    Test sync_ha_alexa_groups skips groups that are already in sync.
    """
    ha_areas = {"Office": ["light.desk"]}
    alexa_groups = [{"name": "Office", "id": "group3", "applianceIds": ["appl4"]}]
    ha_to_alexa = {"Office": ["appl4"]}
    result = sync_ha_alexa_groups(ha_areas, alexa_groups, ha_to_alexa, mode="full")
    assert "Office" in result["skipped"]


def test_find_missing_ha_groups():
    """
    Test find_missing_ha_groups returns correct missing HA areas.
    """
    ha_areas = {"Living Room": [], "Bedroom": []}
    alexa_groups = [{"name": "Living Room"}]
    missing = find_missing_ha_groups(ha_areas, alexa_groups)
    assert missing == ["Bedroom"]


def test_create_alexa_group_for_ha_area(monkeypatch):
    """
    Test create_alexa_group_for_ha_area returns True on successful creation.
    """

    class FakeResponse:
        status_code = 200

    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse())
    result = create_alexa_group_for_ha_area("Office", ["appl1"], "fake_url", {})
    assert result is True


def test_create_alexa_group_for_ha_area_failure(monkeypatch):
    """
    Test create_alexa_group_for_ha_area returns False on failed creation.
    """

    class FakeResponse:
        status_code = 400

    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResponse())
    result = create_alexa_group_for_ha_area("Office", ["appl1"], "fake_url", {})
    assert result is False


def test_sync_alexa_group_entities_update_only(monkeypatch):
    """
    Test sync_alexa_group_entities adds missing entities in update_only mode.
    """
    group = {"id": "group1", "applianceIds": ["appl1"]}
    desired_appliance_ids = ["appl1", "appl2"]
    monkeypatch.setattr("alexa_manager.api.update_alexa_group", lambda *a, **k: True)
    result = sync_alexa_group_entities(
        group, desired_appliance_ids, "update_only", [group], "fake_url", {}
    )
    assert result == "updated"


def test_sync_alexa_group_entities_full(monkeypatch):
    """
    Test sync_alexa_group_entities adds/removes entities in full mode.
    """
    group = {"id": "group2", "applianceIds": ["appl1", "appl2"]}
    desired_appliance_ids = ["appl3"]
    monkeypatch.setattr("alexa_manager.api.update_alexa_group", lambda *a, **k: True)
    result = sync_alexa_group_entities(
        group, desired_appliance_ids, "full", [group], "fake_url", {}
    )
    assert result == "updated"


def test_sync_alexa_group_entities_skipped():
    """
    Test sync_alexa_group_entities skips when already in sync.
    """
    group = {"id": "group3", "applianceIds": ["appl4"]}
    desired_appliance_ids = ["appl4"]
    result = sync_alexa_group_entities(
        group, desired_appliance_ids, "full", [group], "fake_url", {}
    )
    assert result == "skipped"


def test_get_entities_large_response(monkeypatch):
    """
    Test get_entities handles a large response efficiently and correctly.
    """

    class FakeResponse:
        def json(self):
            return [
                {
                    "id": str(i),
                    "displayName": f"Entity {i}",
                    "description": f"Description {i}",
                }
                for i in range(1000)
            ]

        text = "large json"

    monkeypatch.setattr("requests.get", lambda *a, **k: FakeResponse())
    entities = get_entities()
    assert len(entities.entities) == 1000


def test_update_alexa_group_invalid_data():
    """
    Test update_alexa_group handles invalid group data (missing keys).
    """
    groups = [{"name": "Test Group"}]  # Missing 'id'
    updated_fields = {"name": "Updated Group"}
    with pytest.raises(ValueError):
        update_alexa_group("group123", updated_fields, groups)


def test_update_alexa_group_timeout(monkeypatch):
    """
    Test update_alexa_group handles request timeout gracefully.
    """
    groups = [{"id": "group123", "name": "Test Group"}]
    updated_fields = {"name": "Updated Group"}
    import requests

    def raise_timeout(*a, **k):
        raise requests.Timeout("Timeout error")

    monkeypatch.setattr("requests.put", raise_timeout)
    result = update_alexa_group("group123", updated_fields, groups)
    assert result is False


def test_find_group_by_id_duplicate_ids():
    """
    Test find_group_by_id returns the first match when duplicate IDs exist.
    """
    groups = [
        {"id": "dup", "name": "First"},
        {"id": "dup", "name": "Second"},
    ]
    result = find_group_by_id(groups, "dup")
    assert result["name"] == "First"


def test_safe_json_loads_valid():
    """
    Test _safe_json_loads with valid JSON string.
    """
    from alexa_manager.api import _safe_json_loads

    assert _safe_json_loads('{"a": 1}') == {"a": 1}


def test_safe_json_loads_trailing_comma():
    """
    Test _safe_json_loads with trailing comma.
    """
    from alexa_manager.api import _safe_json_loads

    assert _safe_json_loads('{"a": 1,}') == {"a": 1}


def test_safe_json_loads_missing_braces():
    """
    Test _safe_json_loads with missing braces.
    """
    from alexa_manager.api import _safe_json_loads

    assert _safe_json_loads('"a": 1') == {"a": 1}


def test_safe_json_loads_malformed():
    """
    Test _safe_json_loads with malformed input should raise.
    """
    from alexa_manager.api import _safe_json_loads
    import pytest

    with pytest.raises(Exception):
        _safe_json_loads("not a json")


@patch("alexa_manager.api.requests.post")
def test_call_ha_template_api_success(mock_post):
    """
    Test call_ha_template_api returns response text on status 200.
    """
    from alexa_manager.api import call_ha_template_api

    mock_post.return_value.status_code = 200
    mock_post.return_value.text = "ok"
    result = call_ha_template_api({"template": "foo"})
    assert result == "ok"


@patch("alexa_manager.api.requests.post")
def test_call_ha_template_api_non_200(mock_post):
    """
    Test call_ha_template_api returns None on non-200 status.
    """
    from alexa_manager.api import call_ha_template_api

    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "error"
    result = call_ha_template_api({"template": "foo"})
    assert result is None


@patch("alexa_manager.api.requests.post", side_effect=Exception("fail"))
def test_call_ha_template_api_exception(mock_post):
    """
    Test call_ha_template_api returns None on exception.
    """
    from alexa_manager.api import call_ha_template_api

    result = call_ha_template_api({"template": "foo"})
    assert result is None


@patch("alexa_manager.api.requests.post")
def test_get_graphql_endpoint_entities_success(mock_post):
    """
    Test get_graphql_endpoint_entities returns AlexaEntities on valid response.
    """
    from alexa_manager.api import get_graphql_endpoint_entities

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "data": {
            "endpoints": {
                "items": [
                    {
                        "friendlyName": "Lamp",
                        "legacyAppliance": {"applianceId": "appl1"},
                    }
                ]
            }
        }
    }
    entities = get_graphql_endpoint_entities()
    assert hasattr(entities, "entities")
    assert any(e.display_name == "Lamp" for e in entities.entities)


@patch("alexa_manager.api.requests.post")
def test_get_graphql_endpoint_entities_missing_keys(mock_post):
    """
    Test get_graphql_endpoint_entities returns empty AlexaEntities on missing keys.
    """
    from alexa_manager.api import get_graphql_endpoint_entities

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"bad": "data"}
    entities = get_graphql_endpoint_entities()
    assert hasattr(entities, "entities")
    assert len(entities.entities) == 0


@patch("alexa_manager.api.requests.post", side_effect=Exception("fail"))
def test_get_graphql_endpoint_entities_exception(mock_post):
    """
    Test get_graphql_endpoint_entities returns empty AlexaEntities on exception.
    """
    from alexa_manager.api import get_graphql_endpoint_entities

    entities = get_graphql_endpoint_entities()
    assert hasattr(entities, "entities")
    assert len(entities.entities) == 0


def test_normalise_alexa_appliance_id():
    """
    Test _normalise_alexa_appliance_id normalises IDs correctly.
    """
    from alexa_manager.api import _normalise_alexa_appliance_id

    assert _normalise_alexa_appliance_id("SKILL_foo==_sensor#lamp") == "sensor.lamp"
    assert _normalise_alexa_appliance_id("sensor#lamp") == "sensor.lamp"


def test_normalise_ha_entity_id():
    """
    Test _normalise_ha_entity_id returns lowercase.
    """
    from alexa_manager.api import _normalise_ha_entity_id

    assert _normalise_ha_entity_id("Sensor.Lamp") == "sensor.lamp"


def test_map_ha_entities_to_alexa_ids():
    """
    Test map_ha_entities_to_alexa_ids matches normalised IDs.
    """
    from alexa_manager.api import (
        map_ha_entities_to_alexa_ids,
        AlexaEntities,
        AlexaEntity,
    )

    ha_areas = {"Living Room": ["sensor.lamp", "switch.tv"]}
    endpoints = AlexaEntities()
    endpoints.add_entity(
        AlexaEntity(
            entity_id="e1",
            display_name="Lamp",
            description="",
            appliance_id="sensor#lamp",
        )
    )
    endpoints.add_entity(
        AlexaEntity(
            entity_id="e2", display_name="TV", description="", appliance_id="switch#tv"
        )
    )
    result = map_ha_entities_to_alexa_ids(ha_areas, endpoints)
    assert result["Living Room"] == ["sensor#lamp", "switch#tv"]
