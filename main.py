import argparse
import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests

ACCEPT_HEADER = "application/json; charset=utf-8"
DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_LOG_FILE = "app.log"
DEFAULT_USER_AGENT = "AppleWebKit PitanguiBridge/2.2.736478.0-[HARDWARE=iPhone][SOFTWARE=27.0][DEVICE=iPhone]"
GRAPHQL_QUERY = """
query CustomerSmartHome {
    endpoints(endpointsQueryParams: { paginationParams: { disablePagination: true } }) {
        items {
            friendlyName
            legacyAppliance {
                applianceId
                applianceKey
                friendlyDescription
                manufacturerName
            }
        }
    }
}
"""

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    host: str
    cookie: str
    csrf: str
    x_amzn_alexa_app: str
    manufacturer_filter: str
    user_agent: str
    accept_language: str
    timeout: int
    retries: int
    log_file: str
    log_level: str
    save_graphql: str | None
    dry_run: bool


def parse_args():
    parser = argparse.ArgumentParser(
        description="Delete Alexa cloud-connected devices by GraphQL applianceId."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help="Path to optional JSON config file.",
    )
    parser.add_argument(
        "--host", help="Alexa API host, for example eu-api-alexa.amazon.in."
    )
    parser.add_argument(
        "--manufacturer", help="Manufacturer filter, for example SmartLife."
    )
    parser.add_argument("--user-agent", help="User-Agent captured from the Alexa app.")
    parser.add_argument(
        "--accept-language", help="Accept-Language captured from the Alexa app."
    )
    parser.add_argument("--timeout", type=int, help="Request timeout in seconds.")
    parser.add_argument("--retries", type=int, help="Delete retry count per appliance.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching devices without deleting them.",
    )
    parser.add_argument(
        "--save-graphql", help="Optional path to write the raw GraphQL response."
    )
    parser.add_argument("--log-file", help="Path to the log file.")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level."
    )
    return parser.parse_args()


def load_config(path):
    config_path = Path(path)
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf_8") as file:
        return json.load(file)


def config_value(config, *keys):
    for key in keys:
        if key in config and config[key] not in (None, ""):
            return config[key]
    return None


def as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def setting(args, config, arg_name, env_name, *config_keys, default=None):
    arg_value = getattr(args, arg_name, None)
    return (
        arg_value
        or os.getenv(env_name)
        or config_value(config, *config_keys)
        or default
    )


def build_settings(args, config):
    settings = Settings(
        host=setting(args, config, "host", "ALEXA_HOST", "host"),
        cookie=setting(args, config, "cookie", "ALEXA_COOKIE", "cookie"),
        csrf=setting(args, config, "csrf", "ALEXA_CSRF", "csrf"),
        x_amzn_alexa_app=setting(
            args,
            config,
            "x_amzn_alexa_app",
            "ALEXA_X_AMZN_ALEXA_APP",
            "x_amzn_alexa_app",
            "x-amzn-alexa-app",
        ),
        manufacturer_filter=setting(
            args,
            config,
            "manufacturer",
            "ALEXA_MANUFACTURER_FILTER",
            "manufacturer_filter",
            "manufacturer",
            default="SmartLife",
        ),
        user_agent=setting(
            args,
            config,
            "user_agent",
            "ALEXA_USER_AGENT",
            "user_agent",
            default=DEFAULT_USER_AGENT,
        ),
        accept_language=setting(
            args,
            config,
            "accept_language",
            "ALEXA_ACCEPT_LANGUAGE",
            "accept_language",
            default="en-IN,en-US;q=1.0",
        ),
        timeout=int(
            setting(args, config, "timeout", "ALEXA_TIMEOUT", "timeout", default=15)
        ),
        retries=int(
            setting(
                args, config, "retries", "ALEXA_DELETE_RETRIES", "retries", default=4
            )
        ),
        log_file=setting(
            args,
            config,
            "log_file",
            "ALEXA_LOG_FILE",
            "log_file",
            default=DEFAULT_LOG_FILE,
        ),
        log_level=str(
            setting(
                args,
                config,
                "log_level",
                "ALEXA_LOG_LEVEL",
                "log_level",
                default="INFO",
            )
        ).upper(),
        save_graphql=args.save_graphql
        or os.getenv("ALEXA_SAVE_GRAPHQL")
        or config_value(config, "save_graphql"),
        dry_run=args.dry_run
        or as_bool(os.getenv("ALEXA_DRY_RUN"))
        or as_bool(config_value(config, "dry_run")),
    )

    missing = [
        name
        for name in ("host", "cookie", "csrf", "x_amzn_alexa_app")
        if not getattr(settings, name)
    ]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Missing required configuration: {names}. "
            f"Set them in {args.config} or with ALEXA_HOST, ALEXA_COOKIE, "
            "ALEXA_CSRF, and ALEXA_X_AMZN_ALEXA_APP."
        )

    if not hasattr(logging, settings.log_level):
        raise SystemExit(f"Invalid log level: {settings.log_level}")

    return settings


def configure_logging(settings):
    logging.basicConfig(
        filename=settings.log_file,
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=getattr(logging, settings.log_level),
    )


def create_session(settings):
    session = requests.Session()
    session.headers.update(
        {
            "Host": settings.host,
            "Cookie": settings.cookie,
            "Connection": "keep-alive",
            "Accept": ACCEPT_HEADER,
            "Accept-Language": settings.accept_language,
            "User-Agent": settings.user_agent,
            "csrf": settings.csrf,
            "x-amzn-alexa-app": settings.x_amzn_alexa_app,
        }
    )
    return session


def fetch_graphql_endpoints(session, settings):
    url = f"https://{settings.host}/nexus/v1/graphql"
    headers = {
        "Content-Type": ACCEPT_HEADER,
        "x-amzn-RequestId": str(uuid.uuid4()),
    }
    response = session.post(
        url,
        headers=headers,
        json={"query": GRAPHQL_QUERY},
        timeout=settings.timeout,
    )
    response.raise_for_status()
    return response.json()


def matching_endpoints(response_json, manufacturer_filter):
    items = response_json.get("data", {}).get("endpoints", {}).get("items", [])
    filter_text = manufacturer_filter.casefold()

    for item in items:
        legacy_appliance = item.get("legacyAppliance") or {}
        manufacturer_name = str(legacy_appliance.get("manufacturerName", ""))
        if filter_text not in manufacturer_name.casefold():
            continue

        yield {
            "name": item.get("friendlyName")
            or legacy_appliance.get("friendlyName")
            or "Unknown",
            "manufacturer": manufacturer_name,
            "description": str(legacy_appliance.get("friendlyDescription", "")),
            "appliance_id": legacy_appliance.get("applianceId"),
            "appliance_key": legacy_appliance.get("applianceKey"),
        }


def delete_endpoint(session, settings, endpoint):
    appliance_id = endpoint["appliance_id"]
    url = (
        f"https://{settings.host}/api/phoenix/appliance/{quote(appliance_id, safe='')}"
    )

    for attempt in range(1, settings.retries + 1):
        try:
            response = session.delete(
                url,
                headers={
                    "Content-Length": "0",
                    "x-amzn-RequestId": str(uuid.uuid4()),
                },
                timeout=settings.timeout,
            )
        except requests.exceptions.RequestException as error:
            logger.error("Delete request failed for %s: %s", appliance_id, error)
            continue

        logger.debug(
            "Delete response for %s - attempt %s/%s - status %s - text %s",
            appliance_id,
            attempt,
            settings.retries,
            response.status_code,
            response.text,
        )

        if 200 <= response.status_code < 300:
            return True, response.status_code

    return False, response.status_code if "response" in locals() else "request-error"


def print_summary(metrics):
    summary = (
        "\nDeletion summary:\n"
        f"Matched devices: {metrics['matched']}\n"
        f"Dry-run only: {metrics['dry_run']}\n"
        f"Deleted successfully: {metrics['deleted']}\n"
        f"Failed: {metrics['failed']}\n"
        f"Skipped: {metrics['skipped']}"
    )
    print(summary)
    logger.info(summary)


def main():
    args = parse_args()
    config = load_config(args.config)
    settings = build_settings(args, config)
    configure_logging(settings)

    metrics = {
        "matched": 0,
        "dry_run": 0,
        "deleted": 0,
        "failed": 0,
        "skipped": 0,
    }

    with create_session(settings) as session:
        try:
            response_json = fetch_graphql_endpoints(session, settings)
        except (requests.exceptions.RequestException, ValueError) as error:
            raise SystemExit(f"Failed to fetch Alexa endpoints: {error}") from error
        if settings.save_graphql:
            with Path(settings.save_graphql).open("w", encoding="utf_8") as file:
                json.dump(response_json, file, indent=2)

        endpoints = list(
            matching_endpoints(response_json, settings.manufacturer_filter)
        )

        for endpoint in endpoints:
            metrics["matched"] += 1
            appliance_id = endpoint["appliance_id"]
            name = endpoint["name"]

            if not appliance_id:
                metrics["skipped"] += 1
                print(f"SKIP: {name} has no applianceId")
                logger.error(
                    "Skipping %s because it has no applianceId: %s", name, endpoint
                )
                continue

            if settings.dry_run:
                metrics["dry_run"] += 1
                print(f"DRY RUN: would delete {name} ({appliance_id})")
                continue

            success, status_code = delete_endpoint(session, settings, endpoint)
            if success:
                metrics["deleted"] += 1
                print(f"DELETED: {name} ({appliance_id})")
            else:
                metrics["failed"] += 1
                print(f"FAILED: {name} ({appliance_id}) - last status {status_code}")

        if not endpoints:
            print(
                f"No devices matched manufacturer filter: {settings.manufacturer_filter}"
            )

    print_summary(metrics)


if __name__ == "__main__":
    main()
