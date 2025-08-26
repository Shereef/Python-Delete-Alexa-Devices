"""
api.py

API and data processing functions for Alexa management script.

This module contains functions for fetching and processing data from Alexa and Home Assistant APIs.
"""

import json
from typing import Any, Dict, List, Optional
import requests
from alexa_manager import config as dynamic_config
from alexa_manager.config import (
    DEBUG,
    DEBUG_FILES,
    URLS,
    ALEXA_HEADERS,
    HA_HEADERS,
    ALEXA_DEVICE_ID,
    ALEXA_ENTITY_ID,
    ALEXA_DEVICE_DISCOVERY_TIMEOUT,
    IGNORED_HA_AREAS,  # Import ignored areas config
)
from alexa_manager.models import (
    AlexaEntities,
    AlexaEntity,
    AlexaGroups,
    AlexaExpandedGroup,
)
from alexa_manager.utils import (
    rate_limited,
    normalise_area_name,
    convert_normalised_area_to_alexa_name,
)  # Always use this for area normalization
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    stop_after_delay,
    wait_fixed,
    RetryError,
    retry_if_result,
)
import logging

logger = logging.getLogger(__name__)


def _safe_json_loads(text: str) -> Any:
    """
    Safely load JSON from a string, handling trailing commas and missing braces.

    This function removes a trailing comma before the closing brace in a JSON object,
    which is a common formatting error from some template engines. It does not attempt
    to fix deeply malformed JSON, but handles the most frequent edge cases.

    Args:
        text (str): The JSON string to load.

    Returns:
        Any: The loaded JSON object.
    """
    import re

    text = text.strip()
    # Add braces if missing
    if not (text.startswith("{") and text.endswith("}")):
        text = "{" + text + "}"
    # Remove trailing comma before closing brace (object only)
    text = re.sub(r",\s*}", "}", text)
    return json.loads(text)


def _construct_alexa_entity_from_dict(entity_data: Dict[str, Any]) -> AlexaEntity:
    """
    Helper function to construct an AlexaEntity from a dictionary.

    Args:
        entity_data (Dict[str, Any]): Dictionary containing entity data.

    Returns:
        AlexaEntity: The constructed AlexaEntity object.
    """
    return AlexaEntity(
        entity_id=entity_data.get("id")
        or entity_data.get("legacyAppliance", {}).get("applianceKey", ""),
        display_name=entity_data.get("displayName")
        or entity_data.get("friendlyName", ""),
        description=entity_data.get("description")
        or entity_data.get("legacyAppliance", {}).get("friendlyDescription", ""),
        appliance_id=entity_data.get("legacyAppliance", {}).get("applianceId", ""),
    )


@rate_limited
def get_entities(url: str = URLS["GET_ENTITIES"]) -> AlexaEntities:
    """
    Retrieve Alexa skill entities from the specified API endpoint.

    Args:
        url (str): The API endpoint URL.

    Returns:
        AlexaEntities: A collection of AlexaEntity objects.
    """
    parameters = {"skillId": "amzn1.ask.1p.smarthome"}
    try:
        response = requests.get(
            url, headers=ALEXA_HEADERS, params=parameters, timeout=15
        )
        entities = AlexaEntities()
        if response.text.strip():
            try:
                response_json = response.json()
            except json.JSONDecodeError as exc:
                logger.error(
                    f"JSONDecodeError decoding Alexa entities API: {exc}. Response text: {response.text[:100]}"
                )
                return entities
            except Exception as exc:
                logger.error(
                    f"Unexpected error decoding JSON from Alexa entities API: {exc}. Response text: {response.text[:100]}"
                )
                return entities
            for entity_dict in response_json:
                missing_keys = [
                    k
                    for k in ("id", "displayName", "description")
                    if k not in entity_dict
                ]
                if missing_keys:
                    logger.warning(
                        f"Skipping entity with missing keys {missing_keys}: {entity_dict}"
                    )
                    continue
                try:
                    entity = _construct_alexa_entity_from_dict(entity_dict)
                    entities.add_entity(entity)
                except Exception as exc:
                    logger.warning(
                        f"Failed to construct AlexaEntity: {exc}. Entity dict: {entity_dict}"
                    )
                    continue
            if DEBUG:
                logger.debug(f"Loaded {len(entities.entities)} Alexa entities.")
        else:
            logger.warning("Received empty response from Alexa entities API.")
        return entities
    except requests.RequestException as exc:
        logger.error(f"Request error while fetching Alexa entities: {exc}")
        return AlexaEntities()


@rate_limited
def get_graphql_endpoint_entities() -> AlexaEntities:
    """
    Retrieve Alexa endpoint entities using a GraphQL POST request.

    Returns:
        AlexaEntities: A collection of AlexaEntity objects from GraphQL endpoint.
    """
    url = f"https://{URLS['GET_ENTITIES'].split('/')[2]}/nexus/v1/graphql"
    graphql_query = """
        query CustomerSmartHome {
            endpoints(endpointsQueryParams: { paginationParams: { disablePagination: true } }) {
                items {
                    friendlyName
                    legacyAppliance {
                        applianceId
                        mergedApplianceIds
                        connectedVia
                        applianceKey
                        appliancePairs
                        modelName
                        friendlyDescription
                        version
                        friendlyName
                        manufacturerName
                    }
                }
            }
        }
    """
    data = {"query": graphql_query}
    try:
        response = requests.post(url, headers=ALEXA_HEADERS, json=data, timeout=15)
        try:
            response_json = response.json()
        except Exception as exc:
            logger.error(
                f"Error decoding JSON from GraphQL endpoint API: {exc}. Response text: {response.text[:100]}"
            )
            return AlexaEntities()
        entities = AlexaEntities()
        try:
            items = response_json["data"]["endpoints"]["items"]
        except Exception as exc:
            logger.error(
                f"GraphQL response missing expected keys: {exc}. Response JSON: {json.dumps(response_json)[:100]}"
            )
            return entities
        for item in items:
            try:
                entity = _construct_alexa_entity_from_dict(item)
                entities.add_entity(entity)
            except Exception as exc:
                logger.warning(
                    f"Skipping endpoint entity with missing keys: {exc}. Item: {item}"
                )
                continue
        if DEBUG:
            try:
                with open(DEBUG_FILES["graphql"], "w", encoding="utf_8") as file:
                    json.dump(response_json, file)
            except Exception as exc:
                logger.error(f"Failed to write GraphQL debug file: {exc}")
        return entities
    except Exception as exc:
        logger.error(f"Error fetching GraphQL endpoint entities: {exc}")
        return AlexaEntities()


@rate_limited
def get_groups(url: str = URLS["GET_GROUPS"]) -> AlexaGroups:
    """
    Retrieve Alexa groups from the API.

    Args:
        url (str): The API endpoint URL.

    Returns:
        AlexaGroups: A collection of AlexaGroup objects.
    """
    try:
        response = requests.get(url, headers=ALEXA_HEADERS, timeout=15)
        groups = AlexaGroups()
        if response.text.strip():
            try:
                response_json = response.json()
            except Exception as e:
                logger.error(f"Error: Could not decode JSON from Alexa groups API: {e}")
                return groups
            if "applianceGroups" not in response_json:
                logger.error(
                    "Error: 'applianceGroups' key missing in Alexa groups response."
                )
                return groups
            for item in response_json["applianceGroups"]:
                try:
                    expanded_group = AlexaExpandedGroup(
                        name=item.get("name", ""),
                        group_id=item.get("groupId", ""),
                        entity_id=item.get("entityId", ""),
                        entity_type=item.get("entityType", "GROUP"),
                        group_type=item.get("groupType", "APPLIANCE"),
                        child_ids=item.get("childIds", []),
                        defaults=item.get("defaults", []),
                        associated_unit_ids=item.get("associatedUnitIds", []),
                        default_metadata_by_type=item.get("defaultMetadataByType", {}),
                        implicit_targeting_by_type=item.get(
                            "implicitTargetingByType", {}
                        ),
                        appliance_ids=item.get("applianceIds", []),
                    )
                    groups.add_group(expanded_group)
                except Exception as e:
                    logger.error(f"Exception in AlexaExpandedGroup instantiation: {e}")
                    logger.error(f"Problematic group item: {item}")
                    continue
            if DEBUG:
                with open(DEBUG_FILES["groups"], "w", encoding="utf_8") as file:
                    json.dump(response_json["applianceGroups"], file)
        else:
            logger.warning("Empty response received from server.")
        return groups
    except Exception as e:
        logger.error(f"Error fetching Alexa groups: {e}")
        return AlexaGroups()


@rate_limited
@retry(
    retry=retry_if_exception_type((requests.RequestException,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def call_ha_template_api(template: dict) -> Optional[str]:
    """
    Call the Home Assistant template API with the provided template dict.

    Args:
        template (dict): The template payload to send.

    Returns:
        Optional[str]: The response text if successful, None otherwise.
    """
    try:
        response = requests.post(
            URLS["HA_TEMPLATE"],
            headers=HA_HEADERS,
            timeout=15,
            data=json.dumps(template),
        )
        if response.status_code == 200:
            return response.text
        else:
            logger.error(
                f"Failed to call HA template API: {response.status_code} - {response.text}"
            )
            return None
    except Exception as e:
        logger.error(f"Error calling HA template API: {e}")
        return None


@rate_limited
def get_ha_areas() -> Dict[str, List[str]]:
    """
    Fetch Home Assistant areas and their child entity IDs.

    Returns:
        Dict[str, List[str]]: Dictionary mapping area names to lists of entity IDs.
    """
    areas_template = {
        "template": "{%- for area in areas() -%} {{area|to_json}}:{{area_entities(area)|to_json}}, {%- endfor -%}"
    }
    response_text = call_ha_template_api(areas_template)
    if response_text is not None:
        try:
            area_dict = _safe_json_loads(response_text)
            return area_dict
        except Exception as e:
            logger.error(
                f"Error: Could not parse Home Assistant API response as JSON: {e}"
            )
            return {}
    else:
        return {}


def _normalise_alexa_appliance_id(appliance_id: str) -> str:
    """
    Normalise Alexa Appliance ID for comparison with Home Assistant Entity ID.
    Removes SKILL identifier and replaces '#' with '.'.
    Example:
        'SKILL_...==_sensor#back_tap_timer_soil_temperature_1' -> 'sensor.back_tap_timer_soil_temperature_1'
    """
    if "==_" in appliance_id:
        appliance_id = appliance_id.split("==_")[-1]
    return appliance_id.replace("#", ".")


def _normalise_ha_entity_id(ha_entity_id: str) -> str:
    """
    Normalise Home Assistant Entity ID for comparison.
    Returns the entity ID in lowercase.
    Example:
        'sensor.Back_Tap_Timer_Soil_Temperature_1' -> 'sensor.back_tap_timer_soil_temperature_1'
    """
    return ha_entity_id.lower()


def map_ha_entities_to_alexa_ids(
    ha_areas: Dict[str, List[str]], endpoints: AlexaEntities
) -> Dict[str, List[str]]:
    """
    Map Home Assistant entity IDs to Alexa Appliance IDs for each area using normalised exact matching.

    This function ensures that only HA entities with an exact normalised match to an Alexa Appliance ID are mapped.
    The mapping is not based on list order, but on normalised string equality.

    Args:
        ha_areas (Dict[str, List[str]]): Mapping area names to lists of HA entity IDs.
        endpoints (AlexaEntities): AlexaEntities object containing endpoint entities.

    Returns:
        Dict[str, List[str]]: Mapping area names to lists of Alexa applianceIds (only exact matches).
    """
    # Build a lookup of normalised Alexa Appliance IDs to original appliance IDs
    normalised_alexa = {
        _normalise_alexa_appliance_id(e.appliance_id): e.appliance_id
        for e in endpoints.entities
        if e.appliance_id
    }
    area_to_alexa_ids: Dict[str, List[str]] = {}
    for area, ha_ids in ha_areas.items():
        matched_alexa_ids = []
        for ha_id in ha_ids:
            norm_ha_id = _normalise_ha_entity_id(ha_id)
            # Only add Alexa ID if there is an exact normalised match
            if norm_ha_id in normalised_alexa:
                matched_alexa_ids.append(normalised_alexa[norm_ha_id])
        area_to_alexa_ids[area] = matched_alexa_ids
    return area_to_alexa_ids


def find_group_by_id(groups: List[Dict[str, Any]], group_id: str) -> Dict[str, Any]:
    """
    Find a group in the provided list by its ID.

    Args:
        groups (List[Dict[str, Any]]): List of group dictionaries.
        group_id (str): The ID of the group to find.

    Returns:
        Dict[str, Any]: The group dictionary if found.

    Raises:
        ValueError: If the group is not found.
    """
    for g in groups:
        if g.get("id") == group_id:
            return g
    raise ValueError(f"Group with id {group_id} not found in provided groups.")


def put_alexa_group(
    group_data: Dict[str, Any],
    updated_fields: Dict[str, Any],
    url_base: str = URLS["GET_GROUPS"],
    headers: Dict[str, str] = None,
) -> bool:
    """
    Send a PUT request to update a single Alexa group.

    Args:
        group_data (Dict[str, Any]): The original group data.
        updated_fields (Dict[str, Any]): Fields to update in the group.
        url_base (str): Base URL for group operations.
        headers (Dict[str, str]): Headers for the Alexa API requests.

    Returns:
        bool: True if update was successful, False otherwise.

    Note:
        This function does not handle user interaction or confirmation prompts.
        Interactive confirmation should be handled externally (e.g., in main.py).
    """
    from alexa_manager.models import AlexaExpandedGroup

    if headers is None:
        headers = ALEXA_HEADERS

    new_data = group_data.copy()
    new_data.update(updated_fields)

    expanded_group = AlexaExpandedGroup(
        name=new_data.get("name", ""),
        group_id=new_data.get("id", ""),
        entity_id=new_data.get("entityId", ""),
        entity_type=new_data.get("entityType", "GROUP"),
        group_type=new_data.get("groupType", "APPLIANCE"),
        child_ids=new_data.get("childIds", []),
        defaults=new_data.get("defaults", []),
        associated_unit_ids=new_data.get("associatedUnitIds", []),
        default_metadata_by_type=new_data.get("defaultMetadataByType", {}),
        implicit_targeting_by_type=new_data.get("implicitTargetingByType", {}),
        appliance_ids=new_data.get("applianceIds", []),
    )
    payload = expanded_group.to_dict()
    url = f"{url_base}/{expanded_group.id}"
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return True
        else:
            logger.error(
                f"Failed to update group {expanded_group.id}: {response.status_code} {response.text}"
            )
            return False
    except Exception as e:
        logger.error(f"Exception during group update: {e}")
        return False


def update_alexa_group(
    group_id: str,
    updated_fields: Dict[str, Any],
    groups: List[Dict[str, Any]] = None,
    url_base: str = URLS["GET_GROUPS"],
    headers: Dict[str, str] = None,
) -> bool:
    """
    Update a single Alexa group by ID.

    Args:
        group_id (str): The ID of the group to update.
        updated_fields (Dict[str, Any]): Fields to update in the group.
        groups (List[Dict[str, Any]], optional): List of existing group dicts.
        url_base (str): Base URL for group operations.
        headers (Dict[str, str]): Headers for the Alexa API requests.

    Returns:
        bool: True if update was successful, False otherwise.
    """
    if headers is None:
        headers = ALEXA_HEADERS

    if not groups:
        raise ValueError("Groups list must be provided.")
    group_data = find_group_by_id(groups, group_id)
    return put_alexa_group(group_data, updated_fields, url_base, headers)


def update_alexa_groups_batch(
    updates: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
    url_base: str = URLS["GET_GROUPS"],
    headers: Dict[str, str] = None,
) -> Dict[str, bool]:
    """
    Batch update multiple Alexa groups.

    Args:
        updates (List[Dict[str, Any]]): List of dicts with 'group_id' and 'updated_fields'.
        groups (List[Dict[str, Any]]): List of existing group dicts.
        url_base (str): Base URL for group operations.
        headers (Dict[str, str]): Headers for the Alexa API requests.

    Returns:
        Dict[str, bool]: Mapping of group_id to update success (True/False).
    """
    if headers is None:
        headers = ALEXA_HEADERS

    results = {}
    for update in updates:
        group_id = update.get("group_id")
        updated_fields = update.get("updated_fields", {})
        try:
            success = update_alexa_group(
                group_id, updated_fields, groups, url_base, headers
            )
            results[group_id] = success
        except Exception as e:
            logger.error(f"Batch update failed for group {group_id}: {e}")
            results[group_id] = False
    return results


def find_missing_ha_groups(
    ha_areas: Dict[str, List[str]], alexa_groups: List[Dict[str, Any]]
) -> List[str]:
    """
    Find HA areas that do not exist as Alexa groups.

    Args:
        ha_areas (Dict[str, List[str]]): HA area name to entity IDs mapping.
        alexa_groups (List[Dict[str, Any]]): List of Alexa group dicts.

    Returns:
        List[str]: List of HA area names missing in Alexa groups.
    """
    # Normalise Alexa group names for comparison
    alexa_group_names_normalised = {
        normalise_area_name(g.get("name", "")) for g in alexa_groups
    }
    # Only return HA areas whose normalised name is not in Alexa group names
    return [
        area
        for area in ha_areas
        if normalise_area_name(area) not in alexa_group_names_normalised
    ]


def create_alexa_group_for_ha_area(
    area_name: str,
    appliance_ids: List[str],
    url_base: str,
    headers: Dict[str, str] = None,
) -> bool:
    """
    Create an Alexa group for a given HA area with specified appliance IDs.
    Respects the global DRY_RUN flag and does not perform creation if enabled.

    Args:
        area_name (str): Name of the HA area.
        appliance_ids (List[str]): List of Alexa appliance IDs for the area.
        url_base (str): Alexa group API base URL.
        headers (Dict[str, str]): Alexa API headers.

    Returns:
        bool: True if creation was successful, False otherwise (or always True in dry-run mode).
    """
    from alexa_manager.models import AlexaExpandedGroup
    from alexa_manager.config import DRY_RUN

    if headers is None:
        headers = ALEXA_HEADERS

    new_group = AlexaExpandedGroup(
        name=area_name,
        group_id="",
        entity_id="",
        entity_type="GROUP",
        group_type="APPLIANCE",
        child_ids=[],
        defaults=[],
        associated_unit_ids=[],
        default_metadata_by_type={},
        implicit_targeting_by_type={},
        appliance_ids=appliance_ids,
    )
    # Respect dry-run mode: do not perform actual creation
    if DRY_RUN:
        logging.info(
            f"[DRY-RUN] Would create Alexa group for area '{area_name}' with appliance IDs: {appliance_ids}"
        )
        return True
    try:
        response = requests.post(
            url_base, headers=headers, json=new_group.to_dict(), timeout=15
        )
        return response.status_code == 200
    except Exception:
        return False


def sync_alexa_group_entities(
    group: Dict[str, Any],
    desired_appliance_ids: List[str],
    mode: str,
    alexa_groups: List[Dict[str, Any]],
    url_base: str,
    headers: Dict[str, str] = None,
) -> str:
    """
    Sync entities in an Alexa group to match desired appliance IDs.
    Respects global DRY_RUN config: logs intended actions and skips API calls if enabled.

    Args:
        group (Dict[str, Any]): Alexa group dict.
        desired_appliance_ids (List[str]): Desired Alexa appliance IDs for the group.
        mode (str): Sync mode ("update_only" or "full").
        alexa_groups (List[Dict[str, Any]]): List of Alexa group dicts.
        url_base (str): Alexa group API base URL.
        headers (Dict[str, str]): Alexa API headers.

    Returns:
        str: "updated", "skipped", or "error".
    """
    if headers is None:
        headers = ALEXA_HEADERS
    current_ids = set(group.get("applianceIds", []))
    desired_ids = set(desired_appliance_ids)
    if mode == "update_only":
        to_add = list(desired_ids - current_ids)
        if to_add:
            updated_ids = list(current_ids | desired_ids)
            update_fields = {"applianceIds": updated_ids}
            if dynamic_config.DRY_RUN:
                logger.info(
                    f"[DRY-RUN] Would update group '{group['name']}' (ID: {group['id']}) with applianceIds: {updated_ids}"
                )
                return "updated"
            success = update_alexa_group(
                group["id"], update_fields, alexa_groups, url_base, headers
            )
            return "updated" if success else "error"
        else:
            return "skipped"
    elif mode == "full":
        if current_ids != desired_ids:
            update_fields = {"applianceIds": list(desired_ids)}
            if dynamic_config.DRY_RUN:
                logger.info(
                    f"[DRY-RUN] Would update group '{group['name']}' (ID: {group['id']}) with applianceIds: {list(desired_ids)}"
                )
                return "updated"
            success = update_alexa_group(
                group["id"], update_fields, alexa_groups, url_base, headers
            )
            return "updated" if success else "error"
        else:
            return "skipped"
    return "skipped"


def sync_ha_alexa_groups(
    ha_areas: Dict[str, List[str]],
    alexa_groups: List[Dict[str, Any]],
    ha_to_alexa: Dict[str, List[str]],
    mode: str = "update_only",
    sync_groups: bool = True,
    sync_entities: bool = True,
    url_base: str = URLS["GET_GROUPS"],
    headers: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Orchestrate syncing of HA areas/groups with Alexa groups.
    Respects global DRY_RUN config: logs intended actions and skips API calls if enabled.

    Args:
        ha_areas (Dict[str, List[str]]): HA area name to entity IDs mapping.
        alexa_groups (List[Dict[str, Any]]): List of Alexa group dicts.
        ha_to_alexa (Dict[str, List[str]]): HA area name to Alexa applianceIds mapping.
        mode (str): Sync mode ("update_only" or "full").
        sync_groups (bool): If True, sync group creation.
        sync_entities (bool): If True, sync group entities.
        url_base (str): Alexa group API base URL.
        headers (Dict[str, str]): Alexa API headers.

    Returns:
        Dict[str, Any]: Summary of actions taken (created, updated, skipped, errors).
    """
    if headers is None:
        headers = ALEXA_HEADERS
    results = {"created": [], "updated": [], "skipped": [], "errors": []}

    # Build a mapping from normalised area name to original area name
    # This ensures we can filter and map back to the original for group creation
    normalised_to_original = {normalise_area_name(k): k for k in ha_areas.keys()}

    # IGNORED_HA_AREAS is already normalised at config load time using normalise_area_name
    # Only keep areas whose normalised name is not in IGNORED_HA_AREAS
    filtered_normalised = [
        n for n in normalised_to_original if n not in IGNORED_HA_AREAS
    ]

    # For group creation, use the original area name (not normalised)
    if sync_groups:
        filtered_ha_areas = {
            normalised_to_original[n]: ha_areas[normalised_to_original[n]]
            for n in filtered_normalised
        }
        filtered_ha_to_alexa = {
            normalised_to_original[n]: ha_to_alexa.get(normalised_to_original[n], [])
            for n in filtered_normalised
        }
        missing_groups = find_missing_ha_groups(filtered_ha_areas, alexa_groups)
        for area_name in missing_groups:
            appliance_ids = filtered_ha_to_alexa.get(area_name, [])
            # Convert normalised area name to pretty Alexa group name for creation
            pretty_area_name = convert_normalised_area_to_alexa_name(
                normalise_area_name(area_name)
            )
            if dynamic_config.DRY_RUN:
                logger.info(
                    f"[DRY-RUN] Would create Alexa group for HA area '{pretty_area_name}' with applianceIds: {appliance_ids}"
                )
                results["created"].append(pretty_area_name)
            else:
                if create_alexa_group_for_ha_area(
                    pretty_area_name, appliance_ids, url_base, headers
                ):
                    results["created"].append(pretty_area_name)
                else:
                    results["errors"].append(
                        (pretty_area_name, "Failed to create group")
                    )
    # For entity syncing, do not filter ignored areas
    if sync_entities:
        # Build a mapping of normalised Alexa group names to group objects
        alexa_group_by_normalised_name = {
            normalise_area_name(g.get("name")): g for g in alexa_groups
        }
        # Build a mapping of normalised area name to pretty Alexa group name
        pretty_name_by_normalised = {
            normalise_area_name(k): convert_normalised_area_to_alexa_name(
                normalise_area_name(k)
            )
            for k in ha_areas.keys()
        }
        for area_name, ha_entity_ids in ha_areas.items():
            norm_area_name = normalise_area_name(area_name)
            group = alexa_group_by_normalised_name.get(norm_area_name)
            pretty_area_name = pretty_name_by_normalised.get(norm_area_name, area_name)
            if group:
                desired_appliance_ids = ha_to_alexa.get(area_name, [])
                action = sync_alexa_group_entities(
                    group, desired_appliance_ids, mode, alexa_groups, url_base, headers
                )
                if action == "updated":
                    results["updated"].append(pretty_area_name)
                elif action == "skipped":
                    results["skipped"].append(pretty_area_name)
                elif action == "error":
                    results["errors"].append(
                        (pretty_area_name, "Failed to sync entities")
                    )
    return results


@retry(
    retry=retry_if_exception_type(requests.exceptions.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
def send_alexa_command_via_ha_service(alexa_command: str) -> Optional[str]:
    """
    Send an Alexa command via Home Assistant Service using Alexa Media Player integration.
    Retries on transient HTTP errors using tenacity.

    Parameters:
        alexa_command (str): The Alexa command to send (e.g., 'announce', 'routine', 'discover devices').

    Returns:
        Optional[str]: The device_id or entity_id used if the command was sent successfully, None otherwise.
    """
    url = URLS["HA_ALEXA_COMMAND"]
    payload = {
        "media_content_id": alexa_command,
        "media_content_type": "custom",
    }
    if ALEXA_DEVICE_ID:
        payload["device_id"] = ALEXA_DEVICE_ID
        used_id = ALEXA_DEVICE_ID
    elif ALEXA_ENTITY_ID:
        payload["entity_id"] = ALEXA_ENTITY_ID
        used_id = ALEXA_ENTITY_ID
    else:
        # Attempt to fetch the last used Alexa entity_id if not provided
        last_used_entity_id = fetch_last_used_alexa()
        if last_used_entity_id:
            payload["entity_id"] = last_used_entity_id
            used_id = last_used_entity_id
            logger.info(f"Using last used Alexa entity_id: {last_used_entity_id}")
        else:
            logger.error(
                "No Alexa device_id or entity_id specified for HA service call, and could not fetch last used Alexa entity_id."
            )
            raise ValueError(
                "No Alexa device_id or entity_id specified for HA service call, and could not fetch last used Alexa entity_id."
            )
    response = requests.post(url, headers=HA_HEADERS, json=payload, timeout=15)
    if response.status_code == 200:
        return used_id
    else:
        logger.error(
            f"Failed to send Alexa command via HA service: {response.status_code} {response.text}"
        )
        raise requests.HTTPError(
            f"Alexa command failed: {response.status_code} {response.text}"
        )


def alexa_discover_devices() -> Optional[str]:
    """
    Trigger Alexa to discover new devices via Home Assistant Alexa Media Player integration.
    Uses retry logic for reliability.

    Returns:
        Optional[str]: The device_id or entity_id used if successful, None otherwise.
    """
    if dynamic_config.DRY_RUN:
        logger.info(
            "[DRY-RUN] Would trigger Alexa device discovery via HA. Skipping actual call."
        )
        return None
    return send_alexa_command_via_ha_service("discover devices")


def fetch_last_used_alexa() -> str:
    """
    Fetch the entity_id of the last used Alexa device via Home Assistant template API.

    Returns:
        str: The entity_id of the last called Alexa media player, or an empty string if not found.
    """
    last_used_template = {
        "template": "{{ expand(integration_entities('alexa_media') | select('search', 'media_player')) | selectattr('attributes.last_called', 'eq', True) | map(attribute='entity_id') | first }}"
    }
    response_text = call_ha_template_api(last_used_template)
    if response_text is not None:
        entity_id = response_text.strip().strip('"')
        return entity_id if entity_id else ""
    return ""


def wait_for_device_discovery(
    timeout: Optional[int] = None, poll_interval: float = 5.0
) -> bool:
    """
    Wait for Alexa device discovery to complete by monitoring the number of Alexa entities.
    Triggers device discovery and polls until the entity count increases or timeout is reached.

    Args:
        timeout (Optional[int]): Timeout in seconds. Defaults to config value.
        poll_interval (float): How often to poll for new entities (seconds).

    Returns:
        bool: True if new devices were discovered, False if timed out.
    """
    if timeout is None:
        timeout = ALEXA_DEVICE_DISCOVERY_TIMEOUT
    logger = logging.getLogger(__name__)
    try:
        initial_entities = get_entities()
        initial_count = (
            len(initial_entities.entities)
            if hasattr(initial_entities, "entities")
            else 0
        )
    except (requests.RequestException, ValueError, Exception) as e:
        logger.error(f"Failed to fetch initial Alexa entities: {e}")
        return False
    logger.info(f"Initial Alexa entity count: {initial_count}")
    try:
        alexa_discover_devices()
    except (requests.RequestException, RuntimeError, ValueError, Exception) as e:
        logger.error(f"Failed to trigger Alexa device discovery: {e}")
        return False

    # Dry run: Assume discovery completed successfully for workflow purposes.
    if dynamic_config.DRY_RUN:
        logger.info(
            "[DRY-RUN] Skipping polling for new Alexa devices. Assuming discovery completed successfully."
        )
        return True

    def get_entity_count() -> int:
        """
        Helper function to get the current Alexa entity count.
        Returns:
            int: Number of Alexa entities.
        """
        entities = get_entities()
        return len(entities.entities) if hasattr(entities, "entities") else 0

    class DiscoveryState:
        """
        Tracks the state of entity count stability after an increase.
        """

        def __init__(self, initial_count: int, stable_required: int = 3):
            self.initial_count = initial_count
            self.last_counts: list[int] = []
            self.detected_increase = False
            self.stable_required = stable_required

        def update(self, count: int) -> bool:
            if not self.detected_increase:
                if count > self.initial_count:
                    logger.info(
                        f"New Alexa devices discovered! Entity count increased to {count}. Waiting for count to stabilize..."
                    )
                    self.detected_increase = True
                    self.last_counts = [count]
                else:
                    logger.debug(
                        f"No new devices yet. Current count: {count}. Waiting..."
                    )
                    return False
            else:
                self.last_counts.append(count)
                if len(self.last_counts) > self.stable_required:
                    self.last_counts.pop(0)
                if len(self.last_counts) == self.stable_required and all(
                    x == self.last_counts[0] for x in self.last_counts
                ):
                    logger.info(
                        f"Entity count stable for {self.stable_required} consecutive checks at {count}. Discovery complete."
                    )
                    return True
                logger.debug(f"Entity count stability buffer: {self.last_counts}")
            return False

    state = DiscoveryState(initial_count)

    @retry(
        stop=stop_after_delay(timeout),
        wait=wait_fixed(poll_interval),
        retry=retry_if_result(lambda result: not result),
        reraise=True,
    )
    def poll_until_stable() -> bool:
        count = get_entity_count()
        return state.update(count)

    try:
        poll_until_stable()
        return True
    except (RetryError, RuntimeError, Exception) as e:
        logger.warning(
            f"Timeout reached after {timeout} seconds or polling error: {e}. No new Alexa devices discovered."
        )
        return False
