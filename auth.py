#uses azure cil

import json
import shutil
import subprocess

from config import DATAVERSE_URL, TENANT_ID


def _find_azure_cli() -> str:
    """Return the Azure CLI executable path, including Windows cmd shims."""
    for executable in ("az", "az.cmd", "az.exe"):
        path = shutil.which(executable)
        if path:
            return path

    raise RuntimeError(
        "Azure CLI was not found from Python. Install Azure CLI, restart this "
        "terminal so PATH is refreshed, then run `az login --allow-no-subscriptions`."
    )


def get_access_token() -> str:
    
    #Returns a Dataverse access token for the user currently signed in with Azure CLI.

    command = [
        _find_azure_cli(),
        "account",
        "get-access-token",
        "--resource",
        DATAVERSE_URL,
        "--output",
        "json",
    ]

    if TENANT_ID:
        command.extend(["--tenant", TENANT_ID])

    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            "Azure CLI could not provide a Dataverse token. Run `az login` "
            "with the Microsoft account that has access to this Dataverse "
            f"environment. Details: {detail}"
        ) from exc

    try:
        token_payload = json.loads(completed.stdout)
        return token_payload["accessToken"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise RuntimeError(
            "Azure CLI returned an unexpected token response."
        ) from exc
