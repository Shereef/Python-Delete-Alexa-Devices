"""
config.py

Configuration loading and constants for the Alexa management script.

This module centralizes configuration logic and constants, separating them from main.py for better maintainability and clarity.
"""

from typing import Dict, Any
import logging
import os
import sys

try:
    import tomllib
except ImportError:
    raise ImportError("Python 3.11+ is required for tomllib support.")

try:
    from pydantic import BaseModel, ValidationError, Field
except ImportError:
    raise ImportError("pydantic must be installed via uv for config validation.")


# NOTE: Logging is set up twice (here and after config loading) to ensure
# that errors during config loading are captured. The initial setup uses INFO
# level, and is updated to DEBUG/INFO after config is loaded. This is intentional.
def setup_initial_logging() -> None:
    """
    Set up a basic logging configuration at INFO level for early-stage logging.

    Returns:
        None
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def update_logging_level(debug: bool) -> None:
    """
    Update the logging level based on the debug flag from the config.

    Args:
        debug (bool): If True, set logging to DEBUG; otherwise, INFO.

    Returns:
        None
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.getLogger().setLevel(level)


def read_toml_file(filepath: str) -> Dict:
    """
    Read a TOML file and return its contents as a dictionary.

    Args:
        filepath (str): Path to the TOML file.

    Returns:
        Dict: Parsed TOML content.

    Raises:
        FileNotFoundError: If the file does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    with open(filepath, "rb") as f:
        return tomllib.load(f)


def ensure_user_config_exists(global_path: str, user_path: str) -> None:
    """
    Ensure that the user config file exists by copying from the global config if needed.

    Args:
        global_path (str): Path to the global config file.
        user_path (str): Path to the user config file.

    Returns:
        None
    """
    if not os.path.exists(user_path):
        with (
            open(global_path, "r", encoding="utf-8") as src,
            open(user_path, "w", encoding="utf-8") as dst,
        ):
            dst.write(src.read())


class AlexaManagerConfig(BaseModel):
    DEBUG: bool = False
    SHOULD_SLEEP: bool = True
    DO_NOT_DELETE: bool = False
    ALEXA_HOST: str = "localhost"
    COOKIE: str  # Required: Alexa session cookie
    X_AMZN_ALEXA_APP: str = ""  # Optional, but may be required for some endpoints
    CSRF: str = ""  # Optional, but may be required for some endpoints
    DELETE_SKILL: str = ""  # Optional, but may be required for some endpoints
    USER_AGENT: str = "Mozilla/5.0"
    ROUTINE_VERSION: str = "1.0"
    HA_HOST: str = "localhost"
    HA_API_KEY: str = ""  # Optional: Home Assistant API key
    IGNORED_HA_AREAS: list[str] = Field(default_factory=list)
    DESCRIPTION_FILTER_TEXT: str = (
        ""  # Added for compatibility with tests and AlexaEntities
    )
    # New config fields for Alexa Media Player integration
    ALEXA_DEVICE_ID: str = ""
    ALEXA_ENTITY_ID: str = ""


def load_config(
    global_path: str = "config/global_config.toml",
    user_path: str = "config/user_config.toml",
) -> Dict[str, Any]:
    """
    Load and validate configuration from config/global_config.toml and config/user_config.toml.
    Sets up logging at INFO level before config is loaded, then updates log level.

    Returns a dictionary containing all config keys (validated and extra),
    so tests and extensions can access arbitrary keys.

    Args:
        global_path (str): Path to the global config file.
        user_path (str): Path to the user config file.

    Returns:
        Dict[str, Any]: The merged configuration dictionary (validated fields + extra keys).

    Raises:
        SystemExit: If config files are malformed or cannot be loaded/validated.
    """
    setup_initial_logging()
    try:
        global_config = read_toml_file(global_path)
    except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
        logging.error(f"Error loading {global_path}: {e}")
        sys.exit(1)
    ensure_user_config_exists(global_path, user_path)
    try:
        user_config = read_toml_file(user_path)
    except (FileNotFoundError, tomllib.TOMLDecodeError) as e:
        logging.error(f"Error loading {user_path}: {e}")
        sys.exit(1)
    merged_config = {**global_config, **user_config}
    # Validate known fields, but keep all keys for compatibility
    try:
        validated_config = AlexaManagerConfig(**merged_config)
    except ValidationError as e:
        logging.error(f"Configuration validation error: {e}")
        sys.exit(1)
    update_logging_level(validated_config.DEBUG)
    # Return all keys, with validated fields updated
    result = dict(merged_config)
    result.update(validated_config.model_dump())
    return result


# Load config and constants
config: Dict = load_config()

# -----------------------------
# Alexa Management Configuration
# -----------------------------

# Debug and runtime flags
DEBUG: bool = config.get("DEBUG", False)
SHOULD_SLEEP: bool = config.get("SHOULD_SLEEP", True)
DO_NOT_DELETE: bool = config.get("DO_NOT_DELETE", False)
DRY_RUN: bool = False  # Global dry-run flag, set by main.py

# Alexa API connection details
ALEXA_HOST: str = config.get("ALEXA_HOST", "localhost")
COOKIE: str = config.get("COOKIE", "")
X_AMZN_ALEXA_APP: str = config.get("X_AMZN_ALEXA_APP", "")
CSRF: str = config.get("CSRF", "")
DELETE_SKILL: str = config.get("DELETE_SKILL", "")
USER_AGENT: str = config.get("USER_AGENT", "Mozilla/5.0")
ROUTINE_VERSION: str = config.get("ROUTINE_VERSION", "1.0")

# Home Assistant API connection details
HA_HOST: str = config.get("HA_HOST", "localhost")
HA_API_KEY: str = config.get("HA_API_KEY", "")
# Alexa Media Player integration config (loaded from config using pydantic)
ALEXA_DEVICE_ID: str = config.get("ALEXA_DEVICE_ID", "")
ALEXA_ENTITY_ID: str = config.get("ALEXA_ENTITY_ID", "")

# Timeout (in seconds) for waiting for Alexa device discovery to complete
ALEXA_DEVICE_DISCOVERY_TIMEOUT: int = 120  # 2 minutes by default

# Debug file paths for saving API responses
DEBUG_FILES: Dict[str, str] = {
    "entities": "entities_debug.json",
    "groups": "groups_debug.json",
    "graphql": "graphql_debug.json",
}

# -----------------------------
# API URLs
# -----------------------------
URLS: Dict[str, str] = {
    "GET_ENTITIES": f"https://{ALEXA_HOST}/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome",
    "GET_GROUPS": f"https://{ALEXA_HOST}/api/phoenix/group",
    # Use GET_GROUPS as base for CREATE and DELETE group endpoints for maintainability
    "CREATE_GROUP": None,  # Will be set below
    "DELETE_GROUP": None,  # Will be set below
    "DELETE_ENTITIES": f"https://{ALEXA_HOST}/api/phoenix/appliance/{DELETE_SKILL}%3D%3D_",
    "HA_TEMPLATE": f"https://{HA_HOST}/api/template",
    # Add Alexa Media Player command endpoint for HA
    "HA_ALEXA_COMMAND": f"https://{HA_HOST}/api/services/media_player/play_media",
}
# Set CREATE_GROUP and DELETE_GROUP using GET_GROUPS as base
URLS["CREATE_GROUP"] = URLS["GET_GROUPS"]  # POST to this URL to create a group
URLS["DELETE_GROUP"] = URLS["GET_GROUPS"] + "/"  # DELETE with group ID appended

# -----------------------------
# Alexa API Headers
# -----------------------------
ALEXA_HEADERS: Dict[str, str] = {
    "Host": ALEXA_HOST,
    "x-amzn-alexa-app": X_AMZN_ALEXA_APP,
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Accept": "application/json; charset=utf-8",
    "User-Agent": USER_AGENT,
    "csrf": CSRF,
    "Cookie": COOKIE,
}

# -----------------------------
# Home Assistant API Headers
# -----------------------------
HA_HEADERS: Dict[str, str] = {
    "Authorization": f"Bearer {HA_API_KEY}",
    "Content-Type": "application/json",
}

# -----------------------------
# Ignored Home Assistant Areas
# -----------------------------
from alexa_manager.utils import normalise_area_name  # noqa: E402

IGNORED_HA_AREAS: list[str] = [
    normalise_area_name(name) for name in config.get("IGNORED_HA_AREAS", [])
]
