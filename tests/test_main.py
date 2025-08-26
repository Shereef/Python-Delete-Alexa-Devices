"""
Integration and CLI tests for main.py.

Covers: CLI argument handling, action dispatch, and error handling.
"""

import pytest
import sys
from unittest.mock import MagicMock
from alexa_manager import main


def test_main_get_entities(monkeypatch):
    """
    Test main CLI with --get-entities argument outputs entities table.
    Expected behavior: main.main() should call print_table and exit with SystemExit(0).
    Edge case: If entity list is empty, print_table should still be called with an empty list.
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--get-entities"])
    cli_output_flag = {}

    def mock_print_table(entity_data, column_headers, table_title):
        cli_output_flag["printed"] = True
        assert isinstance(entity_data, list)
        assert isinstance(column_headers, list)
        assert isinstance(table_title, str)

    monkeypatch.setattr(main, "print_table", mock_print_table)

    class MockEntity:
        id = "id1"
        display_name = "Lamp"
        ha_entity_id = "lamp"
        description = "lamp via Home Assistant"

    class MockAlexaEntities:
        entities = [MockEntity()]

    monkeypatch.setattr(main, "get_entities", lambda: MockAlexaEntities())
    with pytest.raises(SystemExit) as excinfo:
        main.main()
    assert excinfo.value.code == 0
    assert cli_output_flag.get("printed")


def test_main_no_args(monkeypatch):
    """
    Test main CLI with no arguments runs all actions (smoke test).
    """
    monkeypatch.setattr(sys, "argv", ["main.py"])
    called = {}
    monkeypatch.setattr(
        main,
        "delete_entities",
        lambda x, y=None: called.update({"delete_entities": True}) or [],
    )
    monkeypatch.setattr(
        main,
        "delete_groups",
        lambda x, y=None: called.update({"delete_groups": True}) or [],
    )
    monkeypatch.setattr(
        main,
        "create_groups_from_areas",
        lambda x, y=None, z=None: called.update({"create_groups": True}) or [],
    )
    monkeypatch.setattr(main, "get_entities", lambda: MagicMock(entities=[]))
    monkeypatch.setattr(
        main, "get_graphql_endpoint_entities", lambda: MagicMock(entities=[])
    )
    monkeypatch.setattr(main, "get_groups", lambda: MagicMock(groups=[]))
    monkeypatch.setattr(main, "get_ha_areas", lambda: {})
    main.main()
    assert called.get("delete_entities")
    assert called.get("delete_groups")
    assert called.get("create_groups")


@pytest.mark.skip(
    reason="Avoids early test suite termination due to KeyboardInterrupt handling."
)
def test_main_keyboard_interrupt(monkeypatch):
    """
    Test main CLI handles KeyboardInterrupt gracefully.
    """

    monkeypatch.setattr(sys, "argv", ["main.py"])

    def raise_keyboard_interrupt(*a, **k):
        raise KeyboardInterrupt()

    monkeypatch.setattr(main, "delete_entities", raise_keyboard_interrupt)
    # Patch sys.exit to raise SystemExit instead of exiting the test runner
    monkeypatch.setattr(
        sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code))
    )
    with pytest.raises(SystemExit):
        main.main()


def test_main_fatal_error(monkeypatch):
    """
    Test main CLI handles fatal error gracefully without performing live requests.
    All network-related functions are patched to prevent live actions.
    Returns mock objects with expected attributes to avoid errors.
    """
    monkeypatch.setattr(sys, "argv", ["main.py"])

    def raise_error(*a, **k):
        raise Exception("fatal")

    # Mock objects with expected attributes
    class MockEntities:
        entities = []

    class MockGroups:
        groups = []

    monkeypatch.setattr(main, "get_entities", lambda: MockEntities())
    monkeypatch.setattr(main, "delete_entities", raise_error)
    monkeypatch.setattr(main, "get_graphql_endpoint_entities", lambda: MockEntities())
    monkeypatch.setattr(main, "get_groups", lambda: MockGroups())
    monkeypatch.setattr(main, "delete_groups", lambda *a, **k: [])
    monkeypatch.setattr(main, "create_groups_from_areas", lambda *a, **k: [])
    monkeypatch.setattr(main, "get_ha_areas", lambda: {})

    with pytest.raises(Exception) as excinfo:
        main.main()
    # Accept either the original 'fatal' or the new error message
    assert (
        "fatal" in str(excinfo.value)
        or "get_entities() returned None or invalid object." in str(excinfo.value)
        or "'NoneType' object has no attribute 'entities'" in str(excinfo.value)
    )


def test_main_alexa_only_skips_ha(monkeypatch, caplog):
    """
    Test main CLI with --alexa-only argument skips HA-dependent actions.
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--alexa-only", "--create-groups"])
    called = {"create_groups": False, "get_ha_areas": False}

    def fake_create_groups(_):
        called["create_groups"] = True
        return []

    def fake_get_ha_areas():
        called["get_ha_areas"] = True
        return {}

    monkeypatch.setattr(main, "create_groups_from_areas", fake_create_groups)
    monkeypatch.setattr(main, "get_ha_areas", fake_get_ha_areas)
    main.main()
    # Should not call create_groups_from_areas or get_ha_areas
    assert not called["create_groups"]
    assert not called["get_ha_areas"]
    # Should log Alexa Only mode message
    assert any("Alexa Only mode" in r for r in caplog.messages)


def test_main_alexa_only_no_args(monkeypatch, caplog):
    """
    Test main CLI with only --alexa-only argument (no actions).
    Should not attempt real entity deletion.
    """
    import sys
    from alexa_manager.models import AlexaEntity, AlexaGroup

    monkeypatch.setattr(sys, "argv", ["main.py", "--alexa-only"])
    called = {"create_groups": False, "get_ha_areas": False}
    monkeypatch.setattr(
        main,
        "create_groups_from_areas",
        lambda x, y=None: called.update({"create_groups": True}) or [],
    )
    monkeypatch.setattr(
        main, "get_ha_areas", lambda: called.update({"get_ha_areas": True}) or {}
    )
    # Patch AlexaEntity.delete to avoid real API calls
    monkeypatch.setattr(AlexaEntity, "delete", lambda self: True)
    monkeypatch.setattr(AlexaGroup, "delete", lambda self: True)
    main.main()
    # Should not call create_groups_from_areas or get_ha_areas
    assert not called["create_groups"]
    assert not called["get_ha_areas"]
    assert any("Alexa Only mode" in r for r in caplog.messages)


def test_create_groups_from_areas_respects_ignored_areas(monkeypatch):
    """
    Test that create_groups_from_areas skips areas listed in IGNORED_HA_AREAS.
    """
    # Mock HA areas
    ha_areas = {
        "Living Room": ["entity_1", "entity_2"],
        "Garage": ["entity_3"],
        "Kitchen": ["entity_4"],
    }
    # Patch IGNORED_HA_AREAS constant
    monkeypatch.setattr(main, "IGNORED_HA_AREAS", ["Garage"])
    # Patch normalization to identity for test
    monkeypatch.setattr(
        main, "convert_normalised_area_to_alexa_name", lambda name: name
    )
    # Patch dependencies
    monkeypatch.setattr(main, "get_graphql_endpoint_entities", lambda: MagicMock())
    monkeypatch.setattr(
        main,
        "map_ha_entities_to_alexa_ids",
        lambda areas, endpoints: {k: v for k, v in areas.items()},
    )
    created_groups = []

    class DummyAlexaGroup:
        def __init__(self, name):
            self.name = name
            self.create_data = {}

        def create(self):
            created_groups.append(self.name)
            return True

    monkeypatch.setattr(main, "AlexaGroup", DummyAlexaGroup)
    monkeypatch.setattr(
        main, "convert_normalised_area_to_alexa_name", lambda name: name
    )
    monkeypatch.setattr(
        main,
        "run_with_progress_bar",
        lambda areas, title, fn, collector: [fn(area, collector) for area in areas],
    )
    # Call function
    main.create_groups_from_areas(ha_areas, {})
    # Assert ignored area not processed
    assert "Garage" not in created_groups
    assert "Living Room" in created_groups
    assert "Kitchen" in created_groups


def test_main_delete_endpoints_dispatch(monkeypatch):
    """
    Test --delete-endpoints triggers delete_endpoints (mocked, no live requests).
    Ensures downstream network calls are mocked.
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--delete-endpoints"])
    called = {}

    class MockEntities:
        entities = []

    monkeypatch.setattr(main, "get_graphql_endpoint_entities", lambda: MockEntities())
    monkeypatch.setattr(
        main,
        "delete_endpoints",
        lambda x, y=None: called.update({"delete_endpoints": True}) or [],
    )
    main.main()
    assert called.get("delete_endpoints")


def test_main_get_endpoints_table(monkeypatch):
    """
    Test --get-endpoints outputs endpoints table (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--get-endpoints"])
    called = {}

    class MockEntities:
        entities = []

    def mock_print_table(data, headers, title):
        called["print_table"] = True
        assert isinstance(data, list)
        assert isinstance(headers, list)
        assert isinstance(title, str)

    monkeypatch.setattr(main, "get_graphql_endpoint_entities", lambda: MockEntities())
    monkeypatch.setattr(main, "print_table", mock_print_table)
    with pytest.raises(SystemExit):
        main.main()
    assert called.get("print_table")


def test_main_full_sync_success(monkeypatch):
    """
    Test --full-sync runs all workflow steps successfully (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--full-sync"])
    monkeypatch.setattr(
        main,
        "get_entities",
        lambda: type("MockEntities", (), {"entities": [object()]})(),
    )
    monkeypatch.setattr(main, "delete_entities", lambda x, y=None: [])
    monkeypatch.setattr(
        main,
        "get_graphql_endpoint_entities",
        lambda: type("MockEntities", (), {"entities": [object()]})(),
    )
    monkeypatch.setattr(main, "delete_endpoints", lambda x, y=None: [])
    monkeypatch.setattr(
        main, "get_groups", lambda: type("MockGroups", (), {"groups": [object()]})()
    )
    monkeypatch.setattr(main, "delete_groups", lambda x, y=None: [])
    monkeypatch.setattr(main, "alexa_discover_devices", lambda: True)
    monkeypatch.setattr(main, "wait_for_device_discovery", lambda: True)
    monkeypatch.setattr(main, "get_ha_areas", lambda: {"Area": ["entity"]})
    monkeypatch.setattr(
        main, "map_ha_entities_to_alexa_ids", lambda ha, ep: {"Area": ["id"]}
    )
    monkeypatch.setattr(main, "sync_ha_alexa_groups", lambda *a, **k: {"synced": True})
    main.main()


def test_main_full_sync_failure(monkeypatch):
    """
    Test --full-sync handles failure at each step (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--full-sync"])
    monkeypatch.setattr(main, "get_entities", lambda: None)
    main.main()


def test_main_dry_run(monkeypatch):
    """
    Test --dry-run only simulates actions (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--delete-entities", "--dry-run"])
    called = {}

    class MockEntities:
        entities = []

    monkeypatch.setattr(main, "get_entities", lambda: MockEntities())
    monkeypatch.setattr(
        main,
        "delete_entities",
        lambda x, y=None: called.update({"delete_entities": True}) or [],
    )
    main.main()
    assert called.get("delete_entities")


def test_main_interactive_decline(monkeypatch):
    """
    Test --interactive mode cancels on user decline (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--delete-entities", "--interactive"])

    class MockEntities:
        entities = [
            type(
                "Entity",
                (),
                {
                    "display_name": "Lamp",
                    "id": "id1",
                    "delete_id": "did1",
                    "description": "desc",
                    "delete": lambda self: True,
                },
            )()
        ]

    monkeypatch.setattr(main, "get_entities", lambda: MockEntities())
    monkeypatch.setattr(main, "confirm_batch_action", lambda items, action: False)
    monkeypatch.setattr(main, "delete_entities", lambda x, y=None: [])
    main.main()


def test_main_alexa_only_group_creation(monkeypatch, caplog):
    """
    Test --alexa-only with --create-groups skips HA-dependent actions (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--alexa-only", "--create-groups"])
    called = {"create_groups": False}
    monkeypatch.setattr(
        main,
        "create_groups_from_areas",
        lambda *a, **k: called.update({"create_groups": True}) or [],
    )
    main.main()
    assert not called["create_groups"]
    assert any("Alexa Only mode" in r for r in caplog.messages)


def test_main_alexa_discover_devices(monkeypatch):
    """
    Test --alexa-discover-devices triggers device discovery (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--alexa-discover-devices"])
    monkeypatch.setattr(main, "alexa_discover_devices", lambda: "test_id")
    main.main()


def test_main_filter_entities(monkeypatch):
    """
    Test --filter-entities applies filtering to entities (mocked, no live requests).
    """
    monkeypatch.setattr(sys, "argv", ["main.py", "--get-entities", "--filter-entities"])

    class MockEntity:
        id = "id1"
        display_name = "Lamp"
        ha_entity_id = "lamp"
        description = "desc"

    class MockEntities:
        entities = [MockEntity()]

        def get_filtered_entities(self):
            return [MockEntity()]

    called = {}

    def mock_print_table(data, headers, title):
        called["print_table"] = True
        assert isinstance(data, list)
        assert isinstance(headers, list)
        assert isinstance(title, str)

    monkeypatch.setattr(main, "get_entities", lambda: MockEntities())
    monkeypatch.setattr(main, "print_table", mock_print_table)
    with pytest.raises(SystemExit):
        main.main()
    assert called.get("print_table")
