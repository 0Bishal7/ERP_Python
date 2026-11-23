# CRM Backend

FastAPI backend for the ERP platform. The application exposes versioned endpoints under `/api/v1` and uses PostgreSQL-backed server sessions for browser authentication.

## Run locally

From this directory, start the API with:

```sh
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The interactive API reference is available at `http://127.0.0.1:8000/docs` in local development. Apply migrations and seed the initial permissions, roles, departments, and administrator before signing in.

## Architecture

See [the backend architecture](docs/ARCHITECTURE.md) for module boundaries, dependency rules, database ownership, API composition, security, and the process for adding CRM, HRMS, Accounts, or Inventory capabilities.
