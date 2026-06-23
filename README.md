# Project Tracker - Custom MCP Server (Part 3)

A small Python MCP server exposing five CRUD tools (`CreateProject_mcp`,
`GetProject_mcp`, `SearchProjects_mcp`, `UpdateProject_mcp`,
`DeleteProject_mcp`) backed by your Dataverse **Projects** table.

## How the pieces fit together

| File | What it does |
| --- | --- |
| `config.py` | Loads environment values such as org URL, table names, and choice maps from `.env`. |
| `auth.py` | Gets a Dataverse token for YOU from Azure CLI after you run `az login`. |
| `dataverse_client.py` | All the actual Dataverse Web API calls: create, get, search, update, and delete. |
| `server.py` | Defines the 5 MCP tools and starts the Streamable HTTP server. |
| `test_connection.py` | Standalone script to confirm auth and connectivity, without MCP involved. |

## 1. One-time setup: Azure CLI user auth

This satisfies the "don't use a Service Principal" requirement because
Dataverse calls run as your signed-in Microsoft account.

1. Install Azure CLI if you do not already have it.
2. Sign in with the account that owns or can access your Dataverse table:

```bash
az login
```

If your tenant does not have an Azure subscription, sign in at tenant level:

```bash
az login --tenant <TENANT_ID> --allow-no-subscriptions
```

If your Microsoft account belongs to multiple tenants, keep `TENANT_ID` in
`.env` so the token request targets the tenant that owns the Dataverse
environment.

## 2. Project setup

```bash
cd mcp-dataverse-server
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# now edit .env: DATAVERSE_URL and, if needed, TENANT_ID
# PROJECT_ENTITY_SET / PROJECT_PRIMARY_KEY only need changing if your
# table's actual entity set name isn't "pt_projects" - check under
# Power Apps -> Tables -> Projects -> Advanced options.
# DEFAULT_PROJECT_OWNER_NAME defaults to "Zuhaib Noor".
```

## 3. Sanity check before touching MCP at all

```bash
python test_connection.py
```

This uses your current Azure CLI login and should print a WhoAmI JSON
response. If this fails, run `az login` first and confirm that account has
access to your Dataverse environment; the MCP tools will fail the same way.

## 4. Run the MCP server

```bash
python server.py
```

This starts a **Streamable HTTP** server at `http://127.0.0.1:8000/mcp`.
Leave this running in its own terminal.

You can sanity-check the tool list locally with the MCP Inspector:

```bash
mcp dev server.py
```

## 5. Expose it publicly

Use a tunnel such as ngrok or cloudflared:

```bash
ngrok http 8000
# or
cloudflared tunnel --url http://localhost:8000
```

Copy the public HTTPS URL it gives you and append `/mcp`, for example:

```text
https://abcd1234.ngrok-free.app/mcp
```

## 6. Register it in Copilot Studio

In your **Project Tracker** agent, go to **Tools > Add a tool > New tool >
Model Context Protocol**. Paste the public `/mcp` URL, set authentication to
**None** for this dev/test setup, and create it. Copilot Studio should list
your five tools.

## Notes

- **Choice fields**: the agent talks in plain labels such as "High" or "In Progress"; `dataverse_client.py` translates these to and from the integer values Dataverse stores.
- **Owner is server-controlled**: create/update/search tools do not expose owner as an input. New projects are assigned to the active Dataverse user whose Full Name matches `DEFAULT_PROJECT_OWNER_NAME`, which defaults to "Zuhaib Noor".
- **Error handling**: every tool catches exceptions and returns `{"success": false, "error": "..."}` instead of crashing.
- If your table's entity set name isn't `pt_projects`, update `PROJECT_ENTITY_SET` in `.env`.
