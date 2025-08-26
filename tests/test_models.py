"""
Unit tests for models.py.

Covers: model instantiation, __repr__, and collection logic.
"""

from alexa_manager.models import (
    AlexaEntity,
    AlexaEntities,
    AlexaGroup,
    AlexaGroups,
    HAArea,
    AlexaExpandedGroup,
)
from unittest.mock import patch


class MockAlexaEntity(AlexaEntity):
    def __init__(self):
        super().__init__(
            entity_id="mock_id",
            display_name="MockEntity",
            description="Mock description",
        )


def test_alexa_entity_repr():
    """
    Test __repr__ for AlexaEntity returns expected string.
    """
    entity_instance = AlexaEntity("id1", "Lamp", "lamp via Home Assistant", "appl1")
    repr_result = repr(entity_instance)
    assert "AlexaEntity" in repr_result
    assert "id1" in repr_result
    assert "Lamp" in repr_result
    assert "lamp via Home Assistant" in repr_result
    assert "appl1" in repr_result


def test_alexa_entities_add_and_repr():
    """
    Test adding AlexaEntity to AlexaEntities and __repr__.
    """
    entities = AlexaEntities()
    entity = AlexaEntity("id2", "Switch", "switch via Home Assistant")
    entities.add_entity(entity)
    assert entity in entities.entities
    assert "AlexaEntities" in repr(entities)


def test_ha_area_repr():
    """
    Test __repr__ for HAArea returns expected string.
    """
    area = HAArea("Living Room", ["light.lamp", "switch.tv"])
    result = repr(area)
    assert "Living Room" in result
    assert "light.lamp" in result
    assert "switch.tv" in result


def test_alexa_groups_add_and_repr():
    """
    Test adding AlexaGroup to AlexaGroups and __repr__.
    """
    groups = AlexaGroups()
    group = AlexaGroup("Bedroom", "group1")
    groups.add_group(group)
    assert group in groups.groups
    assert "AlexaGroups" in repr(groups)


def test_alexa_group_repr():
    """
    Test __repr__ for AlexaGroup returns expected string.
    """
    group = AlexaGroup("Kitchen", "group2")
    result = repr(group)
    assert "Kitchen" in result
    assert "group2" in result


def test_alexa_expanded_group_to_dict():
    """
    Test AlexaExpandedGroup to_dict returns expected dictionary.
    The defaults field may be a list of strings if sanitized by the model.
    """
    from alexa_manager.models import AlexaExpandedGroup

    group = AlexaExpandedGroup(
        name="Test Group",
        group_id="group123",
        entity_id="entity123",
        entity_type="GROUP",
        group_type="APPLIANCE",
        child_ids=["child1", "child2"],
        defaults=["{'type': 'default'}"],  # Model sanitizes dicts to strings
        associated_unit_ids=["unit1"],
        default_metadata_by_type={"type": "meta"},
        implicit_targeting_by_type={"type": "target"},
        appliance_ids=["appl1", "appl2"],
    )
    result = group.to_dict()
    assert result["name"] == "Test Group"
    assert result["id"] == "group123"
    assert result["entityId"] == "entity123"
    assert result["entityType"] == "GROUP"
    assert result["groupType"] == "APPLIANCE"
    assert result["childIds"] == ["child1", "child2"]
    # Accept stringified dicts for defaults, as per model sanitization
    assert result["defaults"] == ["{'type': 'default'}"]
    assert result["associatedUnitIds"] == ["unit1"]
    assert result["defaultMetadataByType"] == {"type": "meta"}
    assert result["implicitTargetingByType"] == {"type": "target"}
    assert result["applianceIds"] == ["appl1", "appl2"]


def test_alexa_expanded_group_repr():
    """
    Test __repr__ for AlexaExpandedGroup returns expected string.
    """
    group = AlexaExpandedGroup(name="Test Group", group_id="group123")
    result = repr(group)
    assert "AlexaGroup" in result
    assert "group123" in result
    assert "Test Group" in result


def test_get_request_dry_run():
    """
    Test that GET requests are executed and can be mocked in dry-run mode.
    Ensures unit tests remain DRY and do not make real network calls.
    """
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 404
        entity = MockAlexaEntity()
        # _check_deleted should call requests.get and return True for 404
        result = entity._check_deleted()
        mock_get.assert_called_once()
        assert result is True


def test_alexa_entity_invalid_params():
    """
    Test AlexaEntity raises TypeError for missing required parameters.
    """
    try:
        AlexaEntity()
    except TypeError:
        assert True
    else:
        assert False, "AlexaEntity should raise TypeError for missing params"


def test_alexa_entities_empty():
    """
    Test AlexaEntities handles empty entity list.
    """
    entities = AlexaEntities()
    assert entities.entities == []
    assert "AlexaEntities" in repr(entities)


def test_alexa_entities_large():
    """
    Test AlexaEntities handles a large number of entities.
    """
    entities = AlexaEntities()
    for i in range(1000):
        entities.add_entity(AlexaEntity(str(i), f"Device {i}", "desc"))
    assert len(entities.entities) == 1000


def test_alexa_groups_duplicate_ids():
    """
    Test AlexaGroups allows duplicate group IDs and both are present.
    """
    groups = AlexaGroups()
    group1 = AlexaGroup("Room", "dup")
    group2 = AlexaGroup("Room", "dup")
    groups.add_group(group1)
    groups.add_group(group2)
    assert groups.groups.count(group1) == 1
    assert groups.groups.count(group2) == 1
    assert len(groups.groups) == 2


def test_alexa_group_invalid_params():
    """
    Test AlexaGroup raises TypeError for missing required parameters.
    """
    try:
        AlexaGroup()
    except TypeError:
        assert True
    else:
        assert False, "AlexaGroup should raise TypeError for missing params"


def test_alexa_entities_filtering():
    """
    Test AlexaEntities filtering logic for description text.
    """
    entities = AlexaEntities()
    entities.filter_text = "match"
    e1 = AlexaEntity("1", "Device1", "desc match")
    e2 = AlexaEntity("2", "Device2", "desc no")
    entities.add_entity(e1)
    entities.add_entity(e2)
    filtered = entities.get_filtered_entities()
    assert e1 in filtered
    assert e2 not in filtered


def test_alexa_entities_delete_filtered_entities():
    """
    Test AlexaEntities.delete_filtered_entities deletes only filtered entities.
    Network requests are mocked.
    """
    entities = AlexaEntities()
    entities.filter_text = "delete"
    e1 = AlexaEntity("1", "Device1", "desc delete")
    e2 = AlexaEntity("2", "Device2", "desc keep")
    entities.add_entity(e1)
    entities.add_entity(e2)
    # Patch AlexaEntity.delete to simulate deletion
    from unittest.mock import patch

    with patch.object(AlexaEntity, "delete", return_value=True) as mock_delete:
        deleted_count = entities.delete_filtered_entities()
        assert deleted_count == 1
        mock_delete.assert_called_once()


def test_alexa_entity_delete_dry_run():
    """
    Test AlexaEntity.delete in dry-run mode does not make network requests.
    """
    from unittest.mock import patch

    entity = AlexaEntity("id", "name", "desc")
    with patch("alexa_manager.models.DRY_RUN", True):
        with patch.object(entity, "_simulate_delete", return_value=True) as mock_sim:
            result = entity.delete()
            assert result is True
            mock_sim.assert_called_once()


def test_alexa_entity_delete_api():
    """
    Test AlexaEntity.delete with API call, network requests are mocked.
    """
    from unittest.mock import patch

    entity = AlexaEntity("id", "name", "desc")
    with patch("alexa_manager.models.DRY_RUN", False):
        with patch.object(entity, "_delete_with_retry", return_value=True) as mock_del:
            result = entity.delete()
            assert result is True
            mock_del.assert_called_once()


def test_alexa_group_create_dry_run():
    """
    Test AlexaGroup.create in dry-run mode does not make network requests.
    """
    from unittest.mock import patch

    group = AlexaGroup("name", "id")
    with patch("alexa_manager.models.DRY_RUN", True):
        result = group.create()
        assert result is True


def test_alexa_group_create_api():
    """
    Test AlexaGroup.create with API call, network requests are mocked.
    """
    from unittest.mock import patch

    group = AlexaGroup("name", "id")
    with patch("alexa_manager.models.DRY_RUN", False):
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.raise_for_status = lambda: None
            result = group.create()
            assert result is True
            mock_post.assert_called_once()


def test_alexa_group_delete_dry_run():
    """
    Test AlexaGroup.delete in dry-run mode does not make network requests.
    """
    from unittest.mock import patch

    group = AlexaGroup("name", "id")
    with patch("alexa_manager.models.DRY_RUN", True):
        result = group.delete()
        assert result is True


def test_alexa_group_delete_api():
    """
    Test AlexaGroup.delete with API call, network requests are mocked.
    """
    from unittest.mock import patch

    group = AlexaGroup("name", "id")
    with patch("alexa_manager.models.DRY_RUN", False):
        with patch.object(group, "_delete_with_retry", return_value=True) as mock_del:
            result = group.delete()
            assert result is True
            mock_del.assert_called_once()


def test_alexa_expanded_group_update_dry_run():
    """
    Test AlexaExpandedGroup.update in dry-run mode does not make network requests.
    """
    from unittest.mock import patch

    group = AlexaExpandedGroup("name", "id")
    with patch("alexa_manager.models.DRY_RUN", True):
        result = group.update()
        assert result is True


def test_alexa_expanded_group_update_api():
    """
    Test AlexaExpandedGroup.update with API call, network requests are mocked.
    """
    from unittest.mock import patch

    group = AlexaExpandedGroup("name", "id")
    with patch("alexa_manager.models.DRY_RUN", False):
        with patch("requests.put") as mock_put:
            mock_put.return_value.status_code = 200
            mock_put.return_value.raise_for_status = lambda: None
            result = group.update()
            assert result is True
            mock_put.assert_called_once()


def test_alexa_expanded_group_invalid_types():
    """
    Test AlexaExpandedGroup raises TypeError for invalid types in constructor.
    """
    import pytest

    with pytest.raises(TypeError):
        AlexaExpandedGroup(name=123, group_id="id")
    with pytest.raises(TypeError):
        AlexaExpandedGroup(name="name", group_id=123)
    with pytest.raises(TypeError):
        AlexaExpandedGroup(name="name", group_id="id", entity_id=123)
    with pytest.raises(TypeError):
        AlexaExpandedGroup(name="name", group_id="id", entity_type=123)
    with pytest.raises(TypeError):
        AlexaExpandedGroup(name="name", group_id="id", group_type=123)
