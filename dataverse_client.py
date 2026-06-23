#All the actual Dataverse Web API calls live here

import re
from datetime import date, datetime
from typing import Optional

import requests

from auth import get_access_token
from config import (
    WEB_API_BASE_URL,
    PROJECT_ENTITY_SET,
    PROJECT_PRIMARY_KEY,
    PROJECT_PUBLIC_ID_FIELD,
    USER_ENTITY_SET,
    USER_PRIMARY_KEY,
    DEFAULT_PROJECT_OWNER_NAME,
    STATUS_MAP,
    PRIORITY_MAP,
    USER_ROLE_MAP,
)

# Matches a standard GUID, e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6
_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


# ---------------------------------------------------------------------------
# Small internal helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    """Standard headers every Dataverse Web API call needs."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        # Asks Dataverse to also include human-readable labels for Choice
        # and Lookup columns (e.g. "High" alongside the raw integer 125640002,
        # and the owner's display name alongside their GUID). This means we
        # don't have to maintain a reverse-lookup map for output formatting.
        "Prefer": 'odata.include-annotations="OData.Community.Display.V1.FormattedValue"',
    }


def _check(resp: requests.Response) -> None:
    """Raise a clear, readable error if Dataverse returned a failure."""
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except ValueError:
            detail = resp.text
        raise RuntimeError(f"Dataverse error ({resp.status_code}): {detail}")


def _map_choice(value: str, mapping: dict, field_label: str) -> int:
    """Translate a human label (e.g. 'High') into the Dataverse integer."""
    key = value.strip().lower()
    if key not in mapping:
        valid = ", ".join(sorted(set(mapping.keys())))
        raise ValueError(f"'{value}' is not a valid {field_label}. Valid options: {valid}")
    return mapping[key]


def _is_guid(value: str) -> bool:
    return bool(_GUID_RE.match(value.strip()))


def _escape_odata_string(value: str) -> str:
    """Escape a Python string for use inside a single-quoted OData literal."""
    return value.replace("'", "''")


def _extract_guid_from_entity_id_header(header_value: str) -> str:
    """
    After a successful POST, Dataverse returns the new record's URL in the
    'OData-EntityId' response header, e.g.:
        https://org.crm.dynamics.com/api/data/v9.2/pt_projects(3fa85f64-...)
    We just need the GUID inside the parentheses.
    """
    match = re.search(r"\(([0-9a-fA-F-]{36})\)", header_value or "")
    if not match:
        raise RuntimeError(f"Could not parse new record ID from header: {header_value}")
    return match.group(1)


def _get_current_user_id(token: str) -> str:
    """Looks up the GUID of the currently signed-in user via WhoAmI."""
    resp = requests.get(f"{WEB_API_BASE_URL}/WhoAmI", headers=_headers(token))
    _check(resp)
    return resp.json()["UserId"]


def _resolve_project_guid(token: str, public_project_id: str) -> str:
    """Resolve a user-facing project ID like P-0001 to Dataverse's row GUID."""
    if _is_guid(public_project_id):
        return public_project_id.strip()

    safe_project_id = _escape_odata_string(public_project_id.strip())
    resp = requests.get(
        f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}",
        headers=_headers(token),
        params={
            "$filter": f"{PROJECT_PUBLIC_ID_FIELD} eq '{safe_project_id}'",
            "$select": PROJECT_PRIMARY_KEY,
        },
    )
    _check(resp)
    rows = resp.json().get("value", [])
    if not rows:
        raise ValueError(f"No project found with ID '{public_project_id}'.")
    if len(rows) > 1:
        raise ValueError(f"Multiple projects found with ID '{public_project_id}'.")
    return rows[0][PROJECT_PRIMARY_KEY]


def _resolve_project_owner_id_by_name(token: str, owner_name: str) -> str:
    """Looks up a custom Users row that is allowed to own projects."""
    safe_name = _escape_odata_string(owner_name)
    project_owner_role = USER_ROLE_MAP["project owner"]
    resp = requests.get(
        f"{WEB_API_BASE_URL}/{USER_ENTITY_SET}",
        headers=_headers(token),
        params={
            "$filter": f"pt_fullname eq '{safe_name}' and pt_role eq {project_owner_role}",
            "$select": f"{USER_PRIMARY_KEY},pt_fullname,pt_role",
        },
    )
    _check(resp)
    rows = resp.json().get("value", [])
    if not rows:
        raise ValueError(
            f"No custom user found with full name '{owner_name}' and role 'Project Owner'."
        )
    if len(rows) > 1:
        raise ValueError(
            f"Multiple project-owner users found with full name '{owner_name}'. "
            "Set DEFAULT_PROJECT_OWNER_NAME to a unique user name."
        )
    return rows[0][USER_PRIMARY_KEY]


def _format_record(record: dict) -> dict:
    """Turns a raw Dataverse JSON record into a clean, agent-friendly dict."""
    return {
        "project_id": record.get(PROJECT_PUBLIC_ID_FIELD),
        "dataverse_row_id": record.get(PROJECT_PRIMARY_KEY),
        "name": record.get("pt_name"),
        "description": record.get("pt_description"),
        "status": record.get("pt_status@OData.Community.Display.V1.FormattedValue"),
        "priority": record.get("pt_priority@OData.Community.Display.V1.FormattedValue"),
        "deadline": record.get("pt_deadline"),
        "owner": record.get("_pt_owner_value@OData.Community.Display.V1.FormattedValue"),
    }


_SELECT_FIELDS = (
    f"{PROJECT_PUBLIC_ID_FIELD},{PROJECT_PRIMARY_KEY},"
    "pt_name,pt_description,pt_status,pt_priority,pt_deadline,_pt_owner_value"
)


def _days_until(deadline: Optional[str]) -> Optional[int]:
    if not deadline:
        return None
    try:
        deadline_date = datetime.fromisoformat(deadline[:10]).date()
    except ValueError:
        return None
    return (deadline_date - date.today()).days


def _risk_for_project(project: dict) -> dict:
    status = (project.get("status") or "").lower()
    priority = (project.get("priority") or "").lower()
    days = _days_until(project.get("deadline"))

    if status == "completed":
        risk, reason = "Low", "Project is completed."
    elif status == "blocked":
        risk, reason = "High", "Project is blocked."
    elif days is None:
        risk, reason = "Medium", "Project has no valid deadline."
    elif days < 0:
        risk, reason = "High", f"Project is {abs(days)} day(s) overdue."
    elif days <= 3:
        risk = "High" if priority == "high" else "Medium"
        reason = "Project is due within 3 days."
    elif days <= 7:
        risk = "Medium" if priority in {"high", "medium"} else "Low"
        reason = "Project is due within 7 days."
    elif days <= 14 and priority == "high":
        risk, reason = "Medium", "High-priority project is due within 14 days."
    else:
        risk, reason = "Low", "Project has enough time before its deadline."

    return {
        **project,
        "days_until_deadline": days,
        "delay_risk": risk,
        "risk_reason": reason,
    }


# ---------------------------------------------------------------------------
# CRUD operations - one function per Part 2 tool, same behavior, new transport
# ---------------------------------------------------------------------------

def create_project(
    name: str,
    description: str,
    status: str,
    priority: str,
    deadline: str,
    owner_name: Optional[str] = None,
) -> dict:
    token = get_access_token()

    body = {
        "pt_name": name,
        "pt_description": description,
        "pt_status": _map_choice(status, STATUS_MAP, "status"),
        "pt_priority": _map_choice(priority, PRIORITY_MAP, "priority"),
        "pt_deadline": deadline,  # expects "YYYY-MM-DD"
    }

    owner_id = _resolve_project_owner_id_by_name(
        token,
        owner_name or DEFAULT_PROJECT_OWNER_NAME,
    )
    body["pt_Owner@odata.bind"] = f"/{USER_ENTITY_SET}({owner_id})"

    resp = requests.post(f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}", headers=_headers(token), json=body)
    _check(resp)

    new_row_id = _extract_guid_from_entity_id_header(resp.headers.get("OData-EntityId"))
    created = get_project(new_row_id)
    public_id = created["project_id"] if created else new_row_id
    return {"project_id": public_id, "project": created, "message": f"Project '{name}' created."}


def get_project(project_id_or_name: str) -> Optional[dict]:
    token = get_access_token()

    if _is_guid(project_id_or_name):
        url = f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}({project_id_or_name})"
        resp = requests.get(url, headers=_headers(token), params={"$select": _SELECT_FIELDS})
        if resp.status_code == 404:
            return None
        _check(resp)
        return _format_record(resp.json())

    # Otherwise, treat the input as a public project ID first, then exact name.
    safe_value = _escape_odata_string(project_id_or_name.strip())
    resp = requests.get(
        f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}",
        headers=_headers(token),
        params={
            "$select": _SELECT_FIELDS,
            "$filter": f"{PROJECT_PUBLIC_ID_FIELD} eq '{safe_value}' or pt_name eq '{safe_value}'",
        },
    )
    _check(resp)
    rows = resp.json().get("value", [])
    return _format_record(rows[0]) if rows else None


def search_projects(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner_name: Optional[str] = None,
) -> list:
    token = get_access_token()

    filters = []
    if status:
        filters.append(f"pt_status eq {_map_choice(status, STATUS_MAP, 'status')}")
    if priority:
        filters.append(f"pt_priority eq {_map_choice(priority, PRIORITY_MAP, 'priority')}")
    if owner_name:
        owner_id = _resolve_project_owner_id_by_name(token, owner_name)
        filters.append(f"_pt_owner_value eq {owner_id}")

    params = {"$select": _SELECT_FIELDS}
    if filters:
        params["$filter"] = " and ".join(filters)

    resp = requests.get(f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}", headers=_headers(token), params=params)
    _check(resp)
    return [_format_record(row) for row in resp.json().get("value", [])]


def calculate_delay_risks() -> dict:
    token = get_access_token()
    resp = requests.get(
        f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}",
        headers=_headers(token),
        params={"$select": _SELECT_FIELDS},
    )
    _check(resp)

    projects = [_risk_for_project(_format_record(row)) for row in resp.json().get("value", [])]
    projects.sort(
        key=lambda p: (
            {"High": 0, "Medium": 1, "Low": 2}[p["delay_risk"]],
            999999 if p["days_until_deadline"] is None else p["days_until_deadline"],
        )
    )

    summary = {
        "total_projects": len(projects),
        "high_risk": sum(1 for p in projects if p["delay_risk"] == "High"),
        "medium_risk": sum(1 for p in projects if p["delay_risk"] == "Medium"),
        "low_risk": sum(1 for p in projects if p["delay_risk"] == "Low"),
    }

    return {
        "as_of_date": date.today().isoformat(),
        "summary": summary,
        "projects": projects,
    }


def update_project(
    project_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    owner_name: Optional[str] = None,
) -> None:
    token = get_access_token()

    # Only send fields that were actually provided - PATCH leaves the rest alone.
    body = {}
    if name is not None:
        body["pt_name"] = name
    if description is not None:
        body["pt_description"] = description
    if status is not None:
        body["pt_status"] = _map_choice(status, STATUS_MAP, "status")
    if priority is not None:
        body["pt_priority"] = _map_choice(priority, PRIORITY_MAP, "priority")
    if deadline is not None:
        body["pt_deadline"] = deadline
    if owner_name is not None:
        owner_id = _resolve_project_owner_id_by_name(token, owner_name)
        body["pt_Owner@odata.bind"] = f"/{USER_ENTITY_SET}({owner_id})"

    if not body:
        raise ValueError("No fields provided to update.")

    project_row_id = _resolve_project_guid(token, project_id)
    url = f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}({project_row_id})"
    resp = requests.patch(url, headers=_headers(token), json=body)
    _check(resp)


def delete_project(project_id: str) -> None:
    token = get_access_token()
    project_row_id = _resolve_project_guid(token, project_id)
    url = f"{WEB_API_BASE_URL}/{PROJECT_ENTITY_SET}({project_row_id})"
    resp = requests.delete(url, headers=_headers(token))
    _check(resp)
