import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP

import dataverse_client as dv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "Project Tracker MCP Server",
    host="0.0.0.0",
    port=8000,
    streamable_http_path="/mcp",
)


@mcp.tool(name="CreateProject_mcp")
def create_project_mcp(
    name: str,
    description: str,
    status: str,
    priority: str,
    deadline: str,
    owner_name: Optional[str] = None,
) -> dict:
    """
    Create a new project record in Dataverse.

    Args:
        name: Project name.
        description: Free-text summary of the project.
        status: One of "Not Started", "Inprogress", "Completed", "Blocked".
        priority: One of "Low", "Medium", "High".
        deadline: Target completion date, formatted as YYYY-MM-DD.
        owner_name: Full name of the project owner from the custom Users table.
            The selected user must have role "Project Owner". If omitted,
            defaults to the configured default project owner.
    """
    logger.info(
        f"CreateProject_mcp called with "
        f"name='{name}', status='{status}', "
        f"priority='{priority}', deadline='{deadline}'"        
    )
    try:
        result = dv.create_project(name, description, status, priority, deadline, owner_name)
        logger.info(
            f"Project created successfully. "
            f"Project ID: {result['project_id']}"
        )
        return {"success": True, **result}
    except Exception as e:
        logger.exception(
            f"Failed to create project '{name}'"
        )
        return {"success": False, "error": str(e)}


@mcp.tool(name="GetProject_mcp")
def get_project_mcp(project_id_or_name: str) -> dict:
    """
    Retrieve a single project, looked up by its public project ID
    (for example P-0001) or by its exact Name.

    Args:
        project_id_or_name: The project's public ID, such as P-0001, or its exact Name value.
    """
    logging.info(
        f"[GetProject_mcp] Looking up project: {project_id_or_name}"
    )
    try:
        result = dv.get_project(project_id_or_name)
        if result is None:
            logging.warning(
                f"[GetProject_mcp] No project found matching '{project_id_or_name}'"
            )
            return {"success": False, "error": f"No project found matching '{project_id_or_name}'."}
        
        logging.info(
            f"[GetProject_mcp] Project found successfully: {project_id_or_name}"
        )
        return {"success": True, "project": result}
    except Exception as e:
        logging.exception(
            f"[GetProject_mcp] Failed while retrieving '{project_id_or_name}'"
        )
        return {"success": False, "error": str(e)}


@mcp.tool(name="SearchProjects_mcp")
def search_projects_mcp(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner_name: Optional[str] = None,
) -> dict:
    """
    Search projects by any combination of status, priority, and owner.
    Leave a field empty to skip filtering on it.

    Args:
        status: One of "Not Started", "Inprogress", "Completed", "Blocked".
        priority: One of "Low", "Medium", "High".
        owner_name: Full name of the owner from the custom Users table.
            The selected user must have role "Project Owner".
    """
    logging.info(
        f"[SearchProjects_mcp] Searching projects "
        f"(status={status}, priority={priority}, owner={owner_name})"
    )
    try:
        results = dv.search_projects(status, priority, owner_name)
        logging.info(
            f"[SearchProjects_mcp] Search completed successfully. "
            f"{len(results)} project(s) found."
        )
        return {"success": True, "count": len(results), "projects": results}
    except Exception as e:
        logging.exception(
            "[SearchProjects_mcp] Failed while searching projects"
        )
        return {"success": False, "error": str(e)}


@mcp.tool(name="CalculateDelayRisk_mcp")
def calculate_delay_risk_mcp() -> dict:
    """
    Calculate delay risk for all projects in Dataverse.

    Returns each project's public ID, name, status, priority, deadline, owner,
    days until deadline, delay risk level, and reason. Risk is Low, Medium, or
    High based on status, deadline, and priority.
    """
    logging.info(
        "[CalculateDelayRisk_mcp] Calculating delay risk for all projects."
    )
    try:
        result = dv.calculate_delay_risks()
        logging.info(
            f"[CalculateDelayRisk_mcp] Delay risk calculation completed successfully. "
        )
        return {"success": True, **result}
    except Exception as e:
        logging.exception(
            "[CalculateDelayRisk_mcp] Failed while calculating delay risks."
        )
        return {"success": False, "error": str(e)}


@mcp.tool(name="UpdateProject_mcp")
def update_project_mcp(
    project_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    deadline: Optional[str] = None,
    owner_name: Optional[str] = None,
) -> dict:
    """
    Update one or more fields on an existing project. Only the fields
    you provide are changed - everything else is left as-is.

    Args:
        project_id: Public project ID to update, such as P-0001.
        name: New project name (optional).
        description: New description (optional).
        status: New status (optional): "Not Started", "Inprogress",
            "Completed", or "Blocked".
        priority: New priority (optional): "Low", "Medium", or "High".
        deadline: New deadline, formatted as YYYY-MM-DD (optional).
        owner_name: New owner full name from the custom Users table (optional).
            The selected user must have role "Project Owner".
    """

    logging.info(
        f"[UpdateProject_mcp] Update request received for project_id={project_id} "
        f"(name={name}, status={status}, priority={priority}, deadline={deadline}, owner={owner_name})"
    )
    try:        
        dv.update_project(project_id, name, description, status, priority, deadline, owner_name)
        logging.info(
            f"[UpdateProject_mcp] Project {project_id} updated successfully."
        )
        return {"success": True, "message": f"Project {project_id} updated."}
    except Exception as e:
        logging.exception(
            f"[UpdateProject_mcp] Failed to update project {project_id}"
        )
        return {"success": False, "error": str(e)}


@mcp.tool(name="DeleteProject_mcp")
def delete_project_mcp(project_id: str) -> dict:
    """
    Permanently delete a project from Dataverse.

    Args:
        project_id: Public project ID to delete, such as P-0001.
    """
    logging.info(
        f"[DeleteProject_mcp] Delete request received for project_id={project_id}"
    )
    try:
        dv.delete_project(project_id)
        logging.info(
            f"[DeleteProject_mcp] Project {project_id} deleted successfully."
        )
        return {"success": True, "message": f"Project {project_id} deleted."}
    except Exception as e:
        logging.exception(
            f"[DeleteProject_mcp] Failed to delete project {project_id}"
        )
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
