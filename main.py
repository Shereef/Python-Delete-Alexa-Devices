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

# Settings
DEBUG = False # set this to True if you want to see more output
SHOULD_SLEEP = False # set this to True if you want to add a delay between each delete request
DESCRIPTION_FILTER_TEXT = "Home Assistant"

# CHANGE THESE TO MATCH YOUR SETUP
HOST = "na-api-alexa.amazon.ca"
USER_AGENT = "AppleWebKit PitanguiBridge/2.2.635412.0-[HARDWARE=iPhone17_3][SOFTWARE=18.2][DEVICE=iPhone]"
ROUTINE_VERSION = "3.0.255246"
COOKIE = ';at-acbca="LONG STRING";sess-at-acbca="SHORT STRING";session-id=000-0000000-0000000;session-id-time=2366612930l;session-token=LOING_STRING;ubid-acbca=000-0000000-00000;x-acbca="SHORT_STRING";csrf=NUMBER'
X_AMZN_ALEXA_APP = "LONG_STRING"
CSRF = "NUMBER" # should look something like this: 'somenumber'; should match the cookie 
DELETE_SKILL = "SKILL_LONG_STRING"

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
    GET_HEADERS = {
        "Host": HOST, 
        "Routines-Version": ROUTINE_VERSION ,
        "Cookie": COOKIE,
        "Connection": "keep-alive",
        "x-amzn-alexa-app": X_AMZN_ALEXA_APP,
        "Accept": ACCEPT_HEADER,
        "User-Agent": USER_AGENT,
    }

    parameters = {
        "skillId": "amzn1.ask.1p.smarthome"
    }

    response_json = None
    response = requests.get(url, headers=GET_HEADERS, params=parameters, timeout=15)

    if not response.text.strip():
        print(f"Empty response received from server. Status code: {response.status_code}")
        return None

    if response.status_code != 200:
        print(f"Non-200 response received from server. Status code: {response.status_code}")
        try:
            print("Response text:", response.text)
        except Exception:
            pass
        return None

    # Convert the response content to JSON
    response_json = response.json()

    # Open a file for writing
    with open(DATA_FILE, 'w', encoding="utf_8") as file:
        # Write the JSON data to the file
        json.dump(response_json, file)
    
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
    headers = {
        "x-amzn-RequestId": str(uuid.uuid4()),
        "Host": HOST,
        "User-Agent": USER_AGENT,
        "Cookie": COOKIE,
        "Connection": "keep-alive",
        "Accept": ACCEPT_HEADER,
        "x-amzn-alexa-app": X_AMZN_ALEXA_APP
    }
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
    DELETE_HEADERS = {
    "Host": HOST, 
    "Content-Length": "0",
    "x-amzn-alexa-app": X_AMZN_ALEXA_APP,
    "Connection": "keep-alive",
    "Accept": ACCEPT_HEADER,
    "User-Agent": USER_AGENT,
    "csrf": CSRF,
    "Cookie": COOKIE} 
    # Open the file for reading
    with open(DATA_FILE, 'r', encoding="utf_8") as file:
        # Load the JSON data from the file
        response_json = json.load(file)
        for item in response_json:
            description = str(item["description"])
            if DESCRIPTION_FILTER_TEXT in description:
                entity_id = item["id"]
                name = item["displayName"]
                device_id_for_url = (description).replace(".", "%23").replace(" via Home Assistant","").lower()
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
                        break
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
    headers = {
        "Content-Length": "1839",
        "Cookie": COOKIE,
        "Host": HOST,
        "Connection": "keep-alive",
        "Accept-Language": "en-CA,en-CA;q=1.0,ar-CA;q=0.9",
        "csrf": CSRF,
        "Content-Type": "application/json; charset=utf-8",
        "x-amzn-RequestId": str(uuid.uuid4()),
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip, deflate, br",
        "x-amzn-alexa-app": X_AMZN_ALEXA_APP,
        "Accept": ACCEPT_HEADER
    }
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
    DELETE_HEADERS = {
    "Host": HOST, 
    "Content-Length": "0",
    "x-amzn-alexa-app": X_AMZN_ALEXA_APP,
    "Connection": "keep-alive",
    "Accept": ACCEPT_HEADER,
    "User-Agent": "AppleWebKit PitanguiBridge/2.2.635412.0-[HARDWARE=iPhone17_3][SOFTWARE=18.2][DEVICE=iPhone]",
    "Accept-Language": "en-CA,en-CA;q=1.0,ar-CA;q=0.9",
    "csrf": CSRF,
    "Cookie": COOKIE} 
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
                device_id_for_url = (description).replace(".", "%23").replace(" via Home Assistant","").lower()
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
                        break
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
    entities = get_entities()
    if not entities:
        print("No entities retrieved; skipping delete_entities().")
    else:
        failed_entities = delete_entities()

    graphql = get_graphql_endpoints()
    if not graphql:
        print("No GraphQL endpoints retrieved; skipping delete_endpoints().")
    else:
        failed_endpoints = delete_endpoints()

    if (entities and failed_entities) or (graphql and failed_endpoints):
        print("\nSummary of all failed deletions:")
        if entities and failed_entities:
            print("\nFailed Entities:")
            for failure in failed_entities:
                print(f"Name: '{failure['name']}', Entity ID: '{failure['entity_id']}'")
        if graphql and failed_endpoints:
            print("\nFailed Endpoints:")
            for failure in failed_endpoints:
                print(f"Name: '{failure['name']}', Entity ID: '{failure['entity_id']}'")
    else:
        print(f"Done, removed all entities and endpoints with a manufacturer name matching: {DESCRIPTION_FILTER_TEXT}")
