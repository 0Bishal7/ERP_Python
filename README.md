# ERP Backend

Minimal FastAPI backend for a modular ERP (CRM first). Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload

Browser
   │
   ▼
React (crm-frontend) ──typed OpenAPI client──► FastAPI (crm-backend)
                                                  │
                                                  ├─ core/    config · db · security · logging
                                                  ├─ shared/  auth · users · rbac · audit
                                                  │           files · notifications · events · masters
                                                  └─ modules/ crm ✅   hrms ⏳   accounts ⏳   inventory ⏳
                                                       │
                                                       ▼
                                              Neon (PostgreSQL)
                                             (schema per module)
                                                       │
                                                       ▼
                                          Local ./uploads/  (files, served by FastAPI)
                                          In-process jobs   (FastAPI BackgroundTasks
Where things happen — file structure mapping:

Layer	Folder	Responsibility
Bootstrap	app/main.py, app/bootstrap.py	Create app, mount routers under /api/v1/<module>, register event subscribers, lifespan
Core (pure)	app/core/ — config.py, db/, security/, logging.py, exceptions.py, pagination.py	Framework primitives only. No business rules. DB session, JWT encode/decode, password hashing, base repo, mixins
Shared	app/shared/ — auth/, users/, rbac/, audit/, files/, notifications/, events/, masters/	Cross-cutting platform services. Owns identity (users), permission checks (rbac), audit writer, event bus, global masters
Business modules	app/modules/crm/, later hrms/, accounts/, inventory/	Domain logic. Each has: models.py (tables) → schemas.py (Pydantic I/O) → repository.py (queries) → service.py (business rules) → router.py (HTTP) + permissions.py (codes) + events.py (publishes) + api.py (facade for other modules)
Migrations	alembic/versions/	One linear stream, named YYYYMMDD_HHMM_<seq>_<module>_<desc>.py — runs against Neon
Background jobs	app/tasks/ (background.py, email.py)	FastAPI BackgroundTasks; no Celery, no Redis. Module-owned jobs live with the module
Tests	tests/ mirrors app/ — core/, shared/<svc>/, modules/crm/, permissions/test_matrix.py	Unit + API + permission matrix + e2e
Infra	.env with DATABASE_URL (Neon connection string), Dockerfile, docker-compose.yml (backend only)	No Postgres container — DB lives on Neon. Entrypoint runs alembic upgrade head then uvicorn
Docs	docs/adr/ (decisions), docs/modules/<name>.md (purpose, tables, events, permissions)	ADRs + per-module README