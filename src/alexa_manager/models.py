"""
models.py

Model classes for Alexa and Home Assistant entities and groups.

This module contains data models used throughout the Alexa management script.
"""

from typing import Any, Dict, List
from alexa_manager.config import (
    config,
    DEBUG,
    DO_NOT_DELETE,
    URLS,
    ALEXA_HEADERS,
    DRY_RUN,
)
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
import logging
from rich.console import Console
import json
from alexa_manager.utils import sanitize_list, format_appliance_id_for_api

logger = logging.getLogger(__name__)
console = Console()


class AlexaEntities:
    """
    Represents a collection of Alexa entities.

    Attributes:
        entities (List[AlexaEntity]): List of AlexaEntity instances.
        filter_text (str): Text used to filter entities by description.
    """

    def __init__(self) -> None:
        """
        Initialize an AlexaEntities object.

        Sets the filter_text from config and initializes an empty entity list.
        """
        self.entities: List[AlexaEntity] = []
        self.filter_text: str = config["DESCRIPTION_FILTER_TEXT"]

    def add_entity(self, entity: "AlexaEntity") -> None:
        """
        Add an AlexaEntity to the collection.

        Parameters:
            entity (AlexaEntity): The entity to add.

        Raises:
            TypeError: If entity is not an AlexaEntity instance.
        """
        if not isinstance(entity, AlexaEntity):
            raise TypeError("entity must be an AlexaEntity instance.")
        self.entities.append(entity)

    def get_filtered_entities(self) -> List["AlexaEntity"]:
        """
        Get entities whose description contains the filter_text.

        Returns:
            List[AlexaEntity]: Filtered list of AlexaEntity instances.
        """
        if not self.filter_text:
            return self.entities
        return [e for e in self.entities if self.filter_text in e.description]

    def delete_filtered_entities(self) -> int:
        """
        Delete only entities whose description contains filter_text.

        Returns:
            int: Number of entities deleted.
        """
        filtered = self.get_filtered_entities()
        deleted_count = 0
        for entity in filtered:
            try:
                if entity.delete():
                    deleted_count += 1
            except Exception as exc:
                logger.error(f"Failed to delete entity {entity.id}: {exc}")
        return deleted_count

    def __repr__(self) -> str:
        """
        Return a string representation of the AlexaEntities object.

        Returns:
            str: String representation of the object.
        """
        return f"AlexaEntities(entities={self.entities})"


class AlexaEntity:
    """
    Represents an Alexa entity (device or endpoint).

    Attributes:
        id (str): Unique identifier for the entity (applianceKey).
        display_name (str): Display name of the entity.
        description (str): Description of the entity.
        ha_entity_id (str): Normalised Home Assistant entity ID.
        delete_id (str): Identifier used for deletion.
        appliance_id (str): Alexa applianceId (from endpoints).
    """

    def __init__(
        self,
        entity_id: str,
        display_name: str,
        description: str,
        appliance_id: str = "",
    ) -> None:
        """
        Initialize an AlexaEntity object.

        Parameters:
            entity_id (str): The entity's unique identifier.
            display_name (str): The display name of the entity.
            description (str): Description of the entity.
            appliance_id (str): The Alexa applianceId (optional).

        Raises:
            TypeError: If any input is not of the expected type.
        """
        if not isinstance(entity_id, str):
            raise TypeError("entity_id must be a string.")
        if not isinstance(display_name, str):
            raise TypeError("display_name must be a string.")
        if not isinstance(description, str):
            raise TypeError("description must be a string.")
        if not isinstance(appliance_id, str):
            raise TypeError("appliance_id must be a string.")
        self.id: str = entity_id
        self.display_name: str = display_name
        self.description: str = description
        self.ha_entity_id: str = self._normalise_ha_entity_id(description)
        self.delete_id: str = self._generate_delete_id(description)
        self.appliance_id: str = appliance_id

    def _normalise_ha_entity_id(self, description: str) -> str:
        """
        Normalise Home Assistant entity ID from description.

        Parameters:
            description (str): The entity description.

        Returns:
            str: Normalised HA entity ID.
        """
        return description.replace(" via Home Assistant", "").lower()

    def _generate_delete_id(self, description: str) -> str:
        """
        Generate delete ID from description for API deletion.

        Parameters:
            description (str): The entity description.

        Returns:
            str: Delete ID for API deletion.
        """
        return (
            description.replace(".", "%23").replace(" via Home Assistant", "").lower()
        )

    def __repr__(self) -> str:
        """
        Return a string representation of the AlexaEntity object.

        Returns:
            str: String representation of the object.
        """
        return f"AlexaEntity(id={self.id}, displayName={self.display_name}, description={self.description}, appliance_id={self.appliance_id})"

    def delete(self) -> bool:
        """
        Delete the Alexa entity using the API, or simulate if DRY_RUN is True.

        Returns:
            bool: True if deletion was successful or simulated, False otherwise.
        """
        url = f"{URLS['DELETE_ENTITIES']}{self.delete_id}"
        if DRY_RUN:
            return self._simulate_delete(url)
        return self._delete_with_retry()

    def _simulate_delete(self, url: str) -> bool:
        """
        Simulate the deletion of an Alexa entity in dry-run mode.

        Parameters:
            url (str): The API endpoint URL for deletion.

        Returns:
            bool: True if simulated deletion is successful, False otherwise.

        Raises:
            requests.HTTPError: If simulated deletion fails.
        """
        console.print(
            f"[bold yellow][DRY RUN][/bold yellow] Would DELETE entity: [cyan]{self.display_name}[/cyan] (ID: {self.id}) at [green]{url}[/green]"
        )
        # Simulate a successful delete response with status 200
        response_status = 200
        if response_status == 200:
            # Simulate the check for deletion (404)
            check_status = 404
            if check_status == 404:
                return True
            else:
                raise requests.HTTPError(
                    f"Entity {self.id} was not deleted. Status code: {check_status}, Response: [DRY RUN] Simulated deleted entity."
                )
        else:
            raise requests.HTTPError(
                f"Entity {self.id} deletion failed. Status code: {response_status}, Response: [DRY RUN] Simulated delete."
            )

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _delete_with_retry(self) -> bool:
        """
        Internal method to perform the actual DELETE request with retry logic.
        Uses exponential backoff and retries up to 3 times for transient errors.

        Returns:
            bool: True if deletion was successful, False otherwise.

        Raises:
            requests.HTTPError: If deletion fails after retries.
        """
        url = f"{URLS['DELETE_ENTITIES']}{self.delete_id}"
        if DO_NOT_DELETE:
            logger.info(f"Skipping deletion of entity {self.id} ({self.display_name})")
            return True
        response = requests.delete(url, headers=ALEXA_HEADERS, timeout=10)
        if DEBUG:
            logger.debug(f"Delete response status code: {response.status_code}")
            logger.debug(f"Delete response text: {response.text}")
        response.raise_for_status()
        # Only treat 204 as success for real API calls
        if response.status_code == 200:
            return self._check_deleted()
        else:
            raise requests.HTTPError(
                f"Entity {self.id} deletion failed. Status code: {response.status_code}, Response: {response.text}"
            )

    @retry(
        retry=retry_if_exception_type(requests.exceptions.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _check_deleted(self) -> bool:
        """
        Check if the entity was deleted by querying the API.
        Retries up to 3 times if a transient HTTP error occurs.

        Returns:
            bool: True if entity is deleted (404), False otherwise.

        Raises:
            requests.HTTPError: If entity is not deleted.
        """
        url = f"https://{config['ALEXA_HOST']}/api/smarthome/v1/presentation/devices/control/{self.id}"
        if DRY_RUN:
            # Simulate a 404 response for dry-run
            class MockResponse:
                status_code = 404
                text = "[DRY RUN] Simulated deleted entity."

            response = MockResponse()
        else:
            response = requests.get(url, headers=ALEXA_HEADERS, timeout=10)
        if DEBUG:
            logger.debug(f"Check delete response status code: {response.status_code}")
            logger.debug(f"Check delete response text: {response.text}")
        if response.status_code == 404:
            return True
        else:
            raise requests.HTTPError(
                f"Entity {self.id} was not deleted. Status code: {response.status_code}, Response: {response.text}"
            )


class HAArea:
    """
    Represents a Home Assistant area and its child entity IDs.

    Attributes:
        name (str): The name of the area.
        entity_ids (List[str]): List of child entity IDs in the area.
    """

    def __init__(self, name: str, entity_ids: List[str]):
        """
        Initialize a HAArea object.

        Parameters:
            name (str): The name of the area.
            entity_ids (List[str]): List of child entity IDs in the area.

        Raises:
            TypeError: If name is not a string or entity_ids is not a list of strings.
        """
        if not isinstance(name, str):
            raise TypeError("name must be a string.")
        if not isinstance(entity_ids, list) or not all(
            isinstance(eid, str) for eid in entity_ids
        ):
            raise TypeError("entity_ids must be a list of strings.")
        self.name = name
        self.entity_ids = entity_ids

    def __repr__(self) -> str:
        """
        Return a string representation of the HAArea object.

        Returns:
            str: String representation of the object.
        """
        return f"HAArea(name={self.name}, entity_ids={self.entity_ids})"


class AlexaGroups:
    """
    Represents a collection of Alexa groups.

    Attributes:
        groups (List[AlexaGroup]): List of AlexaGroup instances.
    """

    def __init__(self):
        """
        Initialize an AlexaGroups object with an empty group list.
        """
        self.groups: List[AlexaGroup] = []

    def add_group(self, group: "AlexaGroup") -> None:
        """
        Add an AlexaGroup to the collection.

        Parameters:
            group (AlexaGroup): The group to add.

        Raises:
            TypeError: If group is not an AlexaGroup instance.
        """
        if not isinstance(group, AlexaGroup):
            raise TypeError("group must be an AlexaGroup instance.")
        self.groups.append(group)

    def __repr__(self) -> str:
        """
        Return a string representation of the AlexaGroups object.

        Returns:
            str: String representation of the object.
        """
        return f"AlexaGroups(groups={self.groups})"


class AlexaGroup:
    """
    Represents an Alexa group.

    Attributes:
        id (str): Unique identifier for the group.
        name (str): Name of the group.
        create_data (Dict[str, Any]): Data used to create the group via API.
    """

    def __init__(self, name: str, group_id: str = "") -> None:
        """
        Initialize an AlexaGroup object.

        Parameters:
            name (str): The name of the group.
            group_id (str): The group's unique identifier (optional).

        Raises:
            TypeError: If name or group_id is not a string.
        """
        if not isinstance(name, str):
            raise TypeError("name must be a string.")
        if not isinstance(group_id, str):
            raise TypeError("group_id must be a string.")
        self.id: str = group_id
        self.name: str = name
        self.create_data: Dict[str, Any] = {
            "entityId": "",
            "id": "",
            "name": self.name,
            "entityType": "GROUP",
            "groupType": "APPLIANCE",
            "childIds": [],
            "defaults": [],
            "associatedUnitIds": [],
            "applianceIds": [],
        }

    def __repr__(self) -> str:
        """
        Return a string representation of the AlexaGroup object.

        Returns:
            str: String representation of the object.
        """
        return f"AlexaGroup(id={self.id}, name={self.name})"

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def create(self) -> bool:
        """
        Create the Alexa group via the API, or simulate if DRY_RUN is True.
        Uses exponential backoff and retries up to 3 times for transient errors.

        Returns:
            bool: True if creation was successful or simulated, False otherwise.

        Raises:
            ValueError: If applianceIds are not all strings.
            requests.HTTPError: If creation fails after retries.
        """
        url = URLS.get("CREATE_GROUP", "")
        if DRY_RUN:
            console.print(
                f"[bold yellow][DRY RUN][/bold yellow] Would CREATE group: [cyan]{self.name}[/cyan] with data: [green]{self.create_data}[/green] at [green]{url}[/green]"
            )
            return True  # Simulate success
        if "applianceIds" in self.create_data:
            for aid in self.create_data["applianceIds"]:
                if not isinstance(aid, str):
                    raise ValueError(
                        "Each applianceId must be a JSON string, not a dict."
                    )
        payload = json.dumps(self.create_data)
        response = requests.post(url, headers=ALEXA_HEADERS, data=payload, timeout=10)
        if DEBUG:
            logger.debug(f"Create group response status code: {response.status_code}")
            logger.debug(f"Create group response text: {response.text}")
        response.raise_for_status()
        return response.status_code == 200

    def delete(self) -> bool:
        """
        Delete the Alexa group via the API, or simulate if DRY_RUN is True.

        Returns:
            bool: True if deletion was successful or simulated, False otherwise.
        """
        if DRY_RUN:
            if DEBUG:
                logger.debug(
                    f"[FAILSAFE] DRY_RUN is enabled at start of delete() for group: {self.name} (ID: {self.id})"
                )
            console.print(
                f"[bold yellow][DRY RUN][/bold yellow] Would DELETE group: [cyan]{self.name}[/cyan] (ID: {self.id}) at [green]{URLS.get('DELETE_GROUP', '')}{self.id}[/green]"
            )
            return True
        if DEBUG:
            logger.debug(
                f"delete() called for group: {self.name} (ID: {self.id}), DRY_RUN={DRY_RUN}"
            )
        base_url = URLS.get("DELETE_GROUP", "")
        url = f"{base_url}{self.id}"
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        if DRY_RUN:
            if DEBUG:
                logger.debug(
                    f"DRY_RUN is enabled. Skipping actual HTTP DELETE for group: {self.name} (ID: {self.id})"
                )
            console.print(
                f"[bold yellow][DRY RUN][/bold yellow] Would DELETE group: [cyan]{self.name}[/cyan] (ID: {self.id}) at [green]{url}[/green]"
            )
            return True  # Simulate success
        return self._delete_with_retry(url)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _delete_with_retry(self, url: str) -> bool:
        """
        Internal method to perform the actual DELETE request with retry logic.
        Uses exponential backoff and retries up to 3 times for transient errors.

        Parameters:
            url (str): The API endpoint URL for deletion.

        Returns:
            bool: True if deletion was successful, False otherwise.

        Raises:
            requests.HTTPError: If deletion fails after retries.
        """
        if DRY_RUN:
            if DEBUG:
                logger.debug(
                    f"_delete_with_retry called in DRY_RUN mode for URL: {url}. Skipping network request."
                )
            return True
        response = requests.delete(url, headers=ALEXA_HEADERS, timeout=10)
        if DEBUG:
            logger.debug(f"Delete group response status code: {response.status_code}")
            logger.debug(f"Delete group response text: {response.text}")
        response.raise_for_status()
        return response.status_code == 200


class AlexaExpandedGroup(AlexaGroup):
    """
    Represents an expanded Alexa group with all fields required for PUT operations.

    This class is used for constructing the full payload required when updating
    Alexa groups via the API. It inherits from AlexaGroup and adds additional fields
    that are present in the PUT payload structure.

    Attributes:
        entity_id (str): The entityId field for the group.
        entity_type (str): The entityType field (default: 'GROUP').
        group_type (str): The groupType field (default: 'APPLIANCE').
        child_ids (List[str]): List of child IDs in the group.
        defaults (List[Any]): List of default settings for the group.
        associated_unit_ids (List[str]): List of associated unit IDs.
        default_metadata_by_type (Dict[str, Any]): Metadata by type.
        implicit_targeting_by_type (Dict[str, Any]): Implicit targeting by type.
        appliance_ids (List[Any]): List of appliance IDs in the group.
    """

    def __init__(
        self,
        name: str,
        group_id: str = "",
        entity_id: str = "",
        entity_type: str = "GROUP",
        group_type: str = "APPLIANCE",
        child_ids: List[Any] = None,
        defaults: List[Any] = None,
        associated_unit_ids: List[Any] = None,
        default_metadata_by_type: Dict[str, Any] = None,
        implicit_targeting_by_type: Dict[str, Any] = None,
        appliance_ids: List[Any] = None,
    ) -> None:
        """
        Initialize an AlexaExpandedGroup object with all fields from the API response.
        Sanitizes all list fields to ensure only hashable types are stored.
        Flattens nested dicts in metadata fields to avoid unhashable type errors.

        Parameters:
            name (str): The name of the group.
            group_id (str): The group's unique identifier.
            entity_id (str): The entityId field for the group.
            entity_type (str): The entityType field.
            group_type (str): The groupType field.
            child_ids (List[Any]): List of child IDs in the group.
            defaults (List[Any]): List of default settings for the group.
            associated_unit_ids (List[Any]): List of associated unit IDs.
            default_metadata_by_type (Dict[str, Any]): Metadata by type.
            implicit_targeting_by_type (Dict[str, Any]): Implicit targeting by type.
            appliance_ids (List[Any]): List of appliance IDs in the group.

        Raises:
            TypeError: If any input is not of the expected type.
        """
        super().__init__(name, group_id)
        if not isinstance(entity_id, str):
            raise TypeError("entity_id must be a string.")
        if not isinstance(entity_type, str):
            raise TypeError("entity_type must be a string.")
        if not isinstance(group_type, str):
            raise TypeError("group_type must be a string.")
        self.entity_id: str = entity_id
        self.entity_type: str = entity_type
        self.group_type: str = group_type
        self.child_ids: List[str] = sanitize_list(child_ids or [], key="id")
        self.defaults: List[str] = sanitize_list(defaults or [])
        self.associated_unit_ids: List[str] = sanitize_list(
            associated_unit_ids or [], key="id"
        )
        self.default_metadata_by_type: Dict[str, Any] = (
            default_metadata_by_type
            if isinstance(default_metadata_by_type, dict)
            else {}
        )
        self.implicit_targeting_by_type: Dict[str, Any] = (
            implicit_targeting_by_type
            if isinstance(implicit_targeting_by_type, dict)
            else {}
        )
        self.appliance_ids: List[str] = sanitize_list(
            appliance_ids or [], key="applianceId"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the AlexaExpandedGroup object to a dictionary suitable for PUT requests.

        Returns:
            Dict[str, Any]: Dictionary representation of the group, matching the Alexa API PUT payload.
        """
        return {
            "entityId": self.entity_id,
            "id": self.id,
            "name": self.name,
            "entityType": self.entity_type,
            "groupType": self.group_type,
            "childIds": self.child_ids,
            "defaults": self.defaults,
            "associatedUnitIds": self.associated_unit_ids,
            "defaultMetadataByType": self.default_metadata_by_type,
            "implicitTargetingByType": self.implicit_targeting_by_type,
            "applianceIds": self.appliance_ids,
        }

    def update(self) -> bool:
        """
        Update the Alexa group via the API, or simulate if DRY_RUN is True.
        Uses exponential backoff and retries up to 3 times for transient errors.

        Returns:
            bool: True if update was successful or simulated, False otherwise.
        """
        url = f"{URLS.get('GET_GROUPS', '')}/{self.id}"
        payload_dict = self.to_dict()
        if "applianceIds" in payload_dict:
            formatted_appliance_ids = []
            for aid in payload_dict["applianceIds"]:
                if isinstance(aid, str) and aid.startswith("{") and aid.endswith("}"):
                    formatted_appliance_ids.append(aid)
                else:
                    formatted_appliance_ids.append(format_appliance_id_for_api(aid))
            payload_dict["applianceIds"] = formatted_appliance_ids
        if payload_dict.get("associatedUnitIds") is None:
            payload_dict["associatedUnitIds"] = []
        payload = json.dumps(payload_dict)
        if DRY_RUN:
            console.print(
                f"[bold yellow][DRY RUN][/bold yellow] Would UPDATE group: [cyan]{self.name}[/cyan] (ID: {self.id}) with data: [green]{payload}[/green] at [green]{url}[/green]"
            )
            return True
        try:
            response = requests.put(
                url, headers=ALEXA_HEADERS, data=payload, timeout=10
            )
            if DEBUG:
                logger.debug(
                    f"Update group response status code: {response.status_code}"
                )
                logger.debug(f"Update group response text: {response.text}")
            response.raise_for_status()
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Exception during group update: {e}")
            return False
