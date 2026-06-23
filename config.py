#All values are loaded from a local .env file

import os
from dotenv import load_dotenv

# Looks for a ".env" file in this same folder and loads it into os.environ.
load_dotenv()


def _require_env(name: str) -> str:
    """Fetch a required environment variable, or fail loudly if missing."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Did you create a .env file from .env.example?"
        )
    return value


# --- Dataverse environment -------------------------------------------------

DATAVERSE_URL = _require_env("DATAVERSE_URL").rstrip("/")
TENANT_ID = os.environ.get("TENANT_ID")
CLIENT_ID = os.environ.get("CLIENT_ID")

PROJECT_ENTITY_SET = os.environ.get("PROJECT_ENTITY_SET", "pt_projects")
PROJECT_PRIMARY_KEY = os.environ.get("PROJECT_PRIMARY_KEY", "pt_projectid")
PROJECT_PUBLIC_ID_FIELD = os.environ.get("PROJECT_PUBLIC_ID_FIELD", "pt_id")
USER_ENTITY_SET = os.environ.get("USER_ENTITY_SET", "pt_users")
USER_PRIMARY_KEY = os.environ.get("USER_PRIMARY_KEY", "pt_userid")
DEFAULT_PROJECT_OWNER_NAME = os.environ.get("DEFAULT_PROJECT_OWNER_NAME", "Zuhaib Noor")

API_VERSION = "v9.2"
WEB_API_BASE_URL = f"{DATAVERSE_URL}/api/data/{API_VERSION}"

# --- Choice (option set) value maps -----------------------------------------

STATUS_MAP = {
    "not started": 125640000,
    "inprogress": 125640001,
    "in progress": 125640001,  
    "completed": 125640002,
    "blocked": 125640003,
}

PRIORITY_MAP = {
    "low": 125640000,
    "medium": 125640001,
    "high": 125640002,
}

USER_ROLE_MAP = {
    "employee": 125640000,
    "manager": 125640001,
    "project owner": 125640002,
}
