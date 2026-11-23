# Architecture (Phase 1: shared core, users, roles, login)

Stack: FastAPI, SQLAlchemy 2.0 (async), Alembic, Neon PostgreSQL, Argon2.
Auth: server-side sessions in an httpOnly cookie. No JWT, no OAuth (yet).

## 1. Layers

```
React app  --cookie + X-CSRF-Token-->  FastAPI  -->  Neon PostgreSQL
                                         |
   router (HTTP only)  ->  service (rules)  ->  models (tables)
```

* **router**: parses the request, declares who may call it (`Depends(require("..."))`).
* **service**: business rules, validation, audit entries, `commit()`.
* **models**: SQLAlchemy tables. No business logic.

## 2. Folder map

```
app/
  core/        config, database (Neon), security (Argon2, tokens), errors, base model
  shared/      used by every module
    auth/      login, logout, me, change password, session + CSRF handling
    users/     users and departments (admin CRUD)
    rbac/      permission registry, default roles, scope helper, roles API
    audit/     audit log writer and reader
  modules/
    crm/       first business module (placeholder for now)
    hrms/ ...  added later; they only use `shared`
  scripts/     seed.py (bootstrap), cleanup_sessions.py
alembic/       migrations
tests/
```

## 3. Login flow (sessions, no JWT)

1. `POST /auth/login {email, password}`
2. Server checks the Argon2 hash, lockout rules, and `is_active`.
3. Server creates a row in `auth_sessions` and sets cookie `session_id` (random token, httpOnly,
   SameSite=Lax, Secure in production). **Only the SHA-256 hash of the token is stored.**
4. Response contains the user, permissions, modules, scope and a `csrf_token`.
5. Every later request carries the cookie automatically. Write requests (POST/PATCH/PUT/DELETE)
   must also send `X-CSRF-Token: <csrf_token>`.
6. Logout revokes the session row. Deactivating a user or changing/resetting a password
   revokes sessions immediately, which JWT cannot do without extra work.

Timeouts: idle 8 h (sliding), absolute 72 h. Both configurable.

Login protection: 5 wrong passwords lock the account for 15 minutes. Unknown emails take the same
time as wrong passwords, and the error message is the same, so emails cannot be guessed.

## 4. Authorization

Three levels, all enforced in the backend:

| Level | How | Where |
|---|---|---|
| Module / action | permission codes `module.resource.action` held through roles | `require("crm.lead.create")` |
| Record scope | `user_type`: staff = own, manager = own + direct reports, admin = all | `apply_scope(stmt, Model.owner_id, principal)` |
| Field level | separate Pydantic schemas per role group (added per module) | module `schemas.py` |

* `user_type = admin` holds every permission automatically (no Admin role to maintain).
* A user has one `department` (organisation info) and many `roles` (what they may do).
* **No privilege escalation:** you can only assign roles or grant permissions that you hold yourself;
  only admins can create or modify admins; the last active admin cannot be removed.
* A user with `must_change_password = true` can only call `/auth/me`, `/auth/change-password`
  and `/auth/logout` until the password is changed.

## 5. Data model

```
departments(id, name, code, is_active)
users(id, email*, full_name, password_hash, user_type, department_id, manager_id,
      is_active, must_change_password, failed_login_attempts, locked_until,
      last_login_at, password_changed_at)
roles(id, name*, description, is_system)
permissions(id, code*, module, description)
role_permissions(role_id, permission_id)      user_roles(user_id, role_id)
auth_sessions(id, token_hash*, csrf_token, user_id, created_at, last_seen_at,
              expires_at, revoked_at, ip_address, user_agent)
audit_logs(id, user_id, action, entity, entity_id, details JSONB, ip_address, created_at)
```
`*` = unique. All ids are UUIDs.

## 6. Neon notes

* Use the **pooled** connection string (`-pooler` host) for the app and the **direct** one for Alembic.
  The code switches off prepared-statement caching for the pooler automatically.
* Neon closes idle connections and can scale to zero: the engine uses `pool_pre_ping` and a short
  `pool_recycle`, so the first request after a pause may be slow but will not fail.
* SSL is always on (`sslmode=require` in the URL is translated for asyncpg).

## 7. How a new module plugs in

1. Add its permission codes to `app/shared/rbac/registry.py`; run `python -m app.scripts.seed`.
2. Create `app/modules/<name>/` with `models.py`, `schemas.py`, `service.py`, `router.py`.
3. Guard routes with `require("<name>.<resource>.<action>")`; filter rows with `apply_scope`.
4. Include the router in `app/api.py`; add its tables to `app/shared/models.py`
   (or import them in `alembic/env.py`) and run `alembic revision --autogenerate`.
5. Give users access by adding the codes to a role. No auth code changes.

## 8. Adding JWT/OAuth later

Nothing outside `shared/auth` depends on how the user is identified: every route receives a
`Principal` from `get_principal`. To add JWT or OAuth (Google, Microsoft), change only that
dependency and the login router; roles, permissions, scope and modules stay as they are.

## 9. Known limits of this phase (planned next)

* Login throttling is per account, not per IP (add IP rate limiting at Nginx or with a middleware).
* No email flows yet (forgot password, invite). Admins reset passwords manually.
* No 2FA.
* Team scope covers direct reports only (not deeper levels).
