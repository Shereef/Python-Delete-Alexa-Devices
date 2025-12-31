"""
This script is used to interact with the Amazon Alexa API.

It contains four main functions: `get_entities`, `delete_entities`, `get_graphql_endpoints`, and `delete_endpoints`.

`get_entities` sends a GET request to the specified URL to retrieve entities related to the Amazon Alexa skill.
The response from the GET request is printed to the console and saved to a JSON file if it's not empty.

`delete_entities` sends a DELETE request to the specified URL to remove entities related to the Amazon Alexa skill.
The response from each DELETE request is printed to the console.

`get_graphql_endpoints` sends a POST request to the specified URL to retrieve specific properties of endpoints using a GraphQL query.
The response from the POST request is printed to the console and saved to a JSON file.

`delete_endpoints` sends a DELETE request to the specified URL to remove endpoints related to the Amazon Alexa skill.
The response from each DELETE request is printed to the console.

The script uses predefined headers and parameters for the requests, which are defined as global variables at the top of the script.

This script is intended to be run as a standalone file. When run, it first calls `get_entities` to retrieve the entities,
then calls `delete_entities` to delete them, then calls `get_graphql_endpoints` to retrieve the endpoints,
and finally calls `delete_endpoints` to delete them.
"""
import json
import time # only needed if you want to add a delay between each delete request
import requests
import uuid
import readline  # Fixes macOS terminal input buffer limit (1024 chars)
import argparse
import os

# Settings
DEBUG = False # set this to True if you want to see more output
SHOULD_SLEEP = False # set this to True if you want to add a delay between each delete request
DESCRIPTION_FILTER_TEXT = "Home Assistant"

def extract_csrf_from_cookie(cookie):
    """
    Extracts the CSRF token from a Cookie header string.
    
    Cookie headers use a simpler format than Set-Cookie: name=value; name2=value2
    This function parses the Cookie header format correctly.
    
    Args:
        cookie (str): The cookie string containing csrf=value
        
    Returns:
        str: The CSRF token value, or None if not found
    """
    # Strip leading/trailing whitespace and semicolons
    cookie = cookie.strip().strip(';')
    
    # Split by semicolon to get individual cookie pairs
    cookie_pairs = cookie.split(';')
    
    for pair in cookie_pairs:
        # Strip whitespace from each pair
        pair = pair.strip()
        # Split on first '=' to separate name and value
        if '=' in pair:
            name, value = pair.split('=', 1)
            name = name.strip()
            # Check if this is the csrf cookie
            if name == 'csrf':
                return value.strip()
    
    return None

def transform_device_id_for_url(description):
    """
    Transforms a device description into the format needed for DELETE URL.
    
    Args:
        description: Device description string
    
    Returns:
        str: Transformed device ID for URL
    """
    return description.replace(".", "%23").replace(" via Home Assistant", "").lower()

def build_base_headers():
    """Returns common headers used across requests."""
    return {
        "Host": HOST,
        "Cookie": COOKIE,
        "Connection": "keep-alive",
        "Accept": ACCEPT_HEADER,
        "Accept-Language": "en-CA,en-CA;q=1.0,ar-CA;q=0.9",
        "User-Agent": USER_AGENT,
        "x-amzn-alexa-app": X_AMZN_ALEXA_APP,
    }

def build_get_headers():
    """Returns headers for GET requests."""
    headers = build_base_headers()
    headers["Routines-Version"] = ROUTINE_VERSION
    return headers

def build_delete_headers():
    """Returns headers for DELETE requests."""
    headers = build_base_headers()
    headers["Content-Length"] = "0"
    headers["csrf"] = CSRF
    return headers

def build_graphql_headers():
    """Returns headers for GraphQL POST requests."""
    headers = build_base_headers()
    headers.update({
        "csrf": CSRF,
        "Content-Type": "application/json; charset=utf-8",
        "Accept-Encoding": "gzip, deflate, br",
    })
    return headers

def parse_arguments():
    """
    Parses command-line arguments and environment variables for configuration values.
    
    Returns:
        dict: Dictionary with HOST, COOKIE, X_AMZN_ALEXA_APP, DELETE_SKILL (or None if not provided)
    """
    parser = argparse.ArgumentParser(
        description="Delete Alexa devices. Provide values via command-line args or environment variables to skip prompts."
    )
    parser.add_argument("--host", help="Amazon API host (e.g., na-api-alexa.amazon.com)")
    parser.add_argument("--cookie", help="Full Cookie header value")
    parser.add_argument("--alexa-app", dest="alexa_app", help="x-amzn-alexa-app header value")
    parser.add_argument("--delete-skill", dest="delete_skill", help="DELETE_SKILL value")
    
    args = parser.parse_args()
    
    # Check environment variables if not provided via command line
    config = {
        "HOST": args.host or os.environ.get("ALEXA_HOST"),
        "COOKIE": args.cookie or os.environ.get("ALEXA_COOKIE"),
        "X_AMZN_ALEXA_APP": args.alexa_app or os.environ.get("ALEXA_APP"),
        "DELETE_SKILL": args.delete_skill or os.environ.get("ALEXA_DELETE_SKILL"),
    }
    
    return config

def prompt_user_input(provided_config=None):
    """
    Prompts the user for required configuration values, skipping those already provided.
    
    Args:
        provided_config: Optional dict with HOST, COOKIE, X_AMZN_ALEXA_APP, DELETE_SKILL
    
    Returns:
        tuple: (HOST, COOKIE, X_AMZN_ALEXA_APP, DELETE_SKILL, CSRF)
    """
    if provided_config is None:
        provided_config = {}
    
    print("=" * 80)
    print("Alexa Device Deletion Script - Configuration")
    print("=" * 80)
    print()
    
    # Only show setup instructions if we need to prompt for values
    if not all([provided_config.get("HOST"), provided_config.get("COOKIE"), 
                provided_config.get("X_AMZN_ALEXA_APP"), provided_config.get("DELETE_SKILL")]):
        print("HTTP Sniffer Setup (do this first):")
        print("  1. Open Alexa app and navigate to Devices tab")
        print("  2. Start HTTP Sniffer capture (e.g., HTTP Catcher, Proxyman, HTTP Toolkit)")
        print("  3. Refresh device list in Alexa app")
        print("  4. Delete a device using the Alexa app (to capture DELETE request)")
        print("  5. Stop the capture in your HTTP Sniffer")
        print()
        print("Now extract the following values from your HTTP Sniffer:")
        print()
    
    # Prompt for HOST
    default_host = "na-api-alexa.amazon.com"
    if provided_config.get("HOST"):
        HOST = provided_config["HOST"]
        print(f"✓ Using HOST from arguments: {HOST}")
    else:
        print("HOST:")
        print("  The Amazon API host for your region.")
        print("  Find in: GET /api/behaviors/entities request")
        print("  Examples: 'na-api-alexa.amazon.com', 'eu-api-alexa.amazon.co.uk'")
        print()
        user_input = input(f"Enter HOST (default: {default_host}): ").strip()
        HOST = user_input if user_input else default_host
    print()
    
    # Prompt for COOKIE
    if provided_config.get("COOKIE"):
        COOKIE = provided_config["COOKIE"]
        print(f"✓ Using COOKIE from arguments (length: {len(COOKIE)} characters)")
    else:
        print("COOKIE:")
        print("  The full Cookie header value (will be very long).")
        print("  Find in: Cookie header from GET /api/behaviors/entities request")
        print()
        COOKIE = input("Enter COOKIE: ").strip()
        if not COOKIE:
            raise ValueError("Cookie value cannot be empty. Please provide a valid cookie string.")
    print()
    
    # Extract CSRF from cookie
    CSRF = extract_csrf_from_cookie(COOKIE)
    if not CSRF:
        raise ValueError(
            "ERROR: Could not extract CSRF token from cookie. "
            "Please ensure your cookie contains a 'csrf=value' entry. "
            "Make sure you copied the complete Cookie header from your HTTP Sniffer."
        )
    print(f"✓ CSRF token automatically extracted from cookie: {CSRF}")
    print()
    
    # Prompt for X_AMZN_ALEXA_APP
    if provided_config.get("X_AMZN_ALEXA_APP"):
        X_AMZN_ALEXA_APP = provided_config["X_AMZN_ALEXA_APP"]
        print(f"✓ Using X_AMZN_ALEXA_APP from arguments")
    else:
        print("X_AMZN_ALEXA_APP:")
        print("  The x-amzn-alexa-app header value (base64 encoded app info).")
        print("  Find in: x-amzn-alexa-app header from GET /api/behaviors/entities request")
        print()
        X_AMZN_ALEXA_APP = input("Enter X_AMZN_ALEXA_APP: ").strip()
    print()
    
    # Prompt for DELETE_SKILL
    if provided_config.get("DELETE_SKILL"):
        DELETE_SKILL = provided_config["DELETE_SKILL"]
        print(f"✓ Using DELETE_SKILL from arguments")
    else:
        print("DELETE_SKILL:")
        print("  The skill identifier used in DELETE requests.")
        print("  Find in: DELETE request containing '/api/phoenix/appliance/'")
        print("  Copy the part after 'api/phoenix/appliance/' but before '%3D%3D_'")
        print("  Example format: 'SKILL_abc123abc...' (much longer)")
        print()
        DELETE_SKILL = input("Enter DELETE_SKILL: ").strip()
    print()
    
    print("=" * 80)
    print("Configuration complete!")
    print("=" * 80)
    print()
    
    return HOST, COOKIE, X_AMZN_ALEXA_APP, DELETE_SKILL, CSRF

# Get configuration from command-line args, environment variables, or user prompts
provided_config = parse_arguments()
HOST, COOKIE, X_AMZN_ALEXA_APP, DELETE_SKILL, CSRF = prompt_user_input(provided_config)

# Validate that we have all required values
if not all([HOST, COOKIE, X_AMZN_ALEXA_APP, DELETE_SKILL, CSRF]):
    print("ERROR: Missing required configuration values. Please run the script again.")
    exit(1)

# Constants
USER_AGENT = "AppleWebKit PitanguiBridge/2.2.635412.0-[HARDWARE=iPhone17_3][SOFTWARE=18.2][DEVICE=iPhone]"
ROUTINE_VERSION = "3.0.255246"

# Constants
DATA_FILE = "data.json"
GRAPHQL_FILE = "graphql.json"
GET_URL = f"https://{HOST}/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome"
DELETE_URL = f"https://{HOST}/api/phoenix/appliance/{DELETE_SKILL}%3D%3D_"
ACCEPT_HEADER = "application/json; charset=utf-8"

def get_entities(url = GET_URL): 
    """
    Sends a GET request to the specified URL to retrieve entities related to the Amazon Alexa skill.

    The method uses predefined headers and parameters for the request, and saves the response to a JSON file if it's not empty.

    Args:
        url (str, optional): The URL to send the GET request to. Defaults to f"https://{HOST}/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome".

    Returns:
        dict: The JSON response from the GET request.
    """
    GET_HEADERS = build_get_headers()

    parameters = {
        "skillId": "amzn1.ask.1p.smarthome"
    }

    response = requests.get(url, headers=GET_HEADERS, params=parameters, timeout=15)

    if response.text.strip():
        # Convert the response content to JSON
        response_json = response.json()

        # Open a file for writing
        with open(DATA_FILE, 'w', encoding="utf_8") as file:
            # Write the JSON data to the file
            json.dump(response_json, file)
    else:
        print("Empty response received from server.")
    
    return response_json

def check_device_deleted(entity_id):
    """
    Sends a GET request to check if the device was deleted.

    Args:
        entity_id (str): The ID of the entity to check.

    Returns:
        bool: True if the device was deleted, False otherwise.
    """
    url = f"https://{HOST}/api/smarthome/v1/presentation/devices/control/{entity_id}"
    headers = build_get_headers()
    headers["x-amzn-RequestId"] = str(uuid.uuid4())
    response = requests.get(url, headers=headers, timeout=10)
    if DEBUG:
        print(f"Check device deleted response status code: {response.status_code}")
        print(f"Check device deleted response text: {response.text}")
    return response.status_code == 404


def delete_entities():
    """
    Sends a DELETE request to the specified URL to remove entities related to the Amazon Alexa skill.

    The method uses predefined headers for the request. It reads entity data from a JSON file, and for each entity, 
    it constructs a URL and sends a DELETE request to that URL.

    Returns:
        list: A list of dictionaries containing information about failed deletions.
    """
    failed_deletions = []
    DELETE_HEADERS = build_delete_headers()
    # Open the file for reading
    with open(DATA_FILE, 'r', encoding="utf_8") as file:
        # Load the JSON data from the file
        response_json = json.load(file)
        for item in response_json:
            description = str(item["description"])
            if DESCRIPTION_FILTER_TEXT in description:
                entity_id = item["id"]
                name = item["displayName"]
                device_id_for_url = transform_device_id_for_url(description)
                print(f"Name: '{name}', Entity ID: '{entity_id}', Device ID: '{device_id_for_url}', Description: '{description}'")
                url = f"{DELETE_URL}{device_id_for_url}"

                deletion_success = False
                for attempt in range(4):
                    DELETE_HEADERS["x-amzn-RequestId"] = str(uuid.uuid4())

                    # Send the DELETE request
                    response = requests.delete(url, headers=DELETE_HEADERS, timeout=10)

                    # Log the response details
                    if DEBUG:
                        print(f"Response Status Code: {response.status_code}")
                        print(f"Response Text: {response.text}")

                    # Check if the entity was deleted using the new function
                    if check_device_deleted(entity_id):
                        if DEBUG:
                            print(f"Entity {name}:{entity_id} successfully deleted.")
                        deletion_success = True
                        break
                    else:
                        print(f"Entity {name}:{entity_id} was not deleted. Attempt {attempt + 1}.")
                        # Continue to next attempt instead of breaking
                    
                    if SHOULD_SLEEP:
                        time.sleep(.2)
                
                if not deletion_success:
                    failed_deletions.append({
                        "name": name,
                        "entity_id": entity_id,
                        "device_id": device_id_for_url,
                        "description": description
                    })
    
    if failed_deletions:
        print("\nFailed to delete the following entities:")
        for failure in failed_deletions:
            print(f"Name: '{failure['name']}', Entity ID: '{failure['entity_id']}', Device ID: '{failure['device_id']}', Description: '{failure['description']}'")
    
    return failed_deletions

def get_graphql_endpoints():
    """
    Sends a POST request to the specified URL to retrieve specific properties of endpoints.

    The method uses predefined headers and a GraphQL query for the request, and saves the response to a JSON file.

    Returns:
        dict: The JSON response from the POST request.
    """
    url = f"https://{HOST}/nexus/v1/graphql"
    headers = build_graphql_headers()
    headers["x-amzn-RequestId"] = str(uuid.uuid4())
    data = {
        "query": """
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
    }
    response = requests.post(url, headers=headers, json=data, timeout=15)
    response_json = response.json()

    # Open a file for writing
    with open(GRAPHQL_FILE, 'w', encoding="utf_8") as file:
        # Write the JSON data to the file
        json.dump(response_json, file)
    # print(json.dumps(response_json, indent=4))
    return response_json

def delete_endpoints():
    """
    Sends a DELETE request to the specified URL to remove endpoints related to the Amazon Alexa skill.

    The method uses predefined headers for the request. It reads endpoint data from a JSON file, and for each endpoint, 
    it constructs a URL and sends a DELETE request to that URL.

    Returns:
        list: A list of dictionaries containing information about failed deletions.
    """
    failed_deletions = []
    DELETE_HEADERS = build_delete_headers()
    # Open the file for reading
    with open(GRAPHQL_FILE, 'r', encoding="utf_8") as file:
        # Load the JSON data from the file
        response_json = json.load(file)
        for item in response_json["data"]["endpoints"]["items"]:
            description = str(item["legacyAppliance"]["friendlyDescription"])
            manufacturer_name = str(item["legacyAppliance"]["manufacturerName"])
            if DESCRIPTION_FILTER_TEXT in manufacturer_name:
                entity_id = item["legacyAppliance"]["applianceKey"]
                name = item["friendlyName"]
                device_id_for_url = transform_device_id_for_url(description)
                print(f"Name: '{name}', Entity ID: '{entity_id}', Device ID: '{device_id_for_url}', Description: '{description}'")
                url = f"{DELETE_URL}{device_id_for_url}"

                deletion_success = False
                for attempt in range(4):
                    DELETE_HEADERS["x-amzn-RequestId"] = str(uuid.uuid4())

                    # Send the DELETE request
                    response = requests.delete(url, headers=DELETE_HEADERS, timeout=10)

                    # Log the response details
                    if DEBUG:
                        print(f"Response Status Code: {response.status_code}")
                        print(f"Response Text: {response.text}")

                    # Check if the entity was deleted using the new function
                    if check_device_deleted(entity_id):
                        if DEBUG:
                            print(f"Entity {name}:{entity_id} successfully deleted.")
                        deletion_success = True
                        break
                    else:
                        print(f"Entity {name}:{entity_id} was not deleted. Attempt {attempt + 1}.")
                        # Continue to next attempt instead of breaking
                    
                    if SHOULD_SLEEP:
                        time.sleep(.2)
                
                if not deletion_success:
                    failed_deletions.append({
                        "name": name,
                        "entity_id": entity_id,
                        "device_id": device_id_for_url,
                        "description": description
                    })
    
    if failed_deletions:
        print("\nFailed to delete the following endpoints:")
        for failure in failed_deletions:
            print(f"Name: '{failure['name']}', Entity ID: '{failure['entity_id']}', Device ID: '{failure['device_id']}', Description: '{failure['description']}'")
    
    return failed_deletions

if __name__ == "__main__":
    get_entities()
    failed_entities = delete_entities()
    get_graphql_endpoints()
    failed_endpoints = delete_endpoints()
    
    if failed_entities or failed_endpoints:
        print("\nSummary of all failed deletions:")
        if failed_entities:
            print("\nFailed Entities:")
            for failure in failed_entities:
                print(f"Name: '{failure['name']}', Entity ID: '{failure['entity_id']}'")
        if failed_endpoints:
            print("\nFailed Endpoints:")
            for failure in failed_endpoints:
                print(f"Name: '{failure['name']}', Entity ID: '{failure['entity_id']}'")
    else:
        print(f"Done, removed all entities and endpoints with a manufacturer name matching: {DESCRIPTION_FILTER_TEXT}")

