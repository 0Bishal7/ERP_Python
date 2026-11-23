from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

API = "/api/v1"


async def _create_sales_user(client, admin_headers):
    roles = (await client.get(f"{API}/roles")).json()
    sales_role = next(r for r in roles if r["name"] == "Sales Staff")
    r = await client.post(
        f"{API}/users",
        headers=admin_headers,
        json={
            "email": "Sam.Sales@example.com",
            "full_name": "Sam Sales",
            "password": "Sales-pass-12345",
            "user_type": "staff",
            "role_ids": [sales_role["id"]],
            "must_change_password": False,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_admin_creates_user_and_roles_apply(client):
    admin_headers = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    user = await _create_sales_user(client, admin_headers)
    assert user["email"] == "sam.sales@example.com"  # normalised
    assert [r["name"] for r in user["roles"]] == ["Sales Staff"]
    await client.post(f"{API}/auth/logout", headers=admin_headers)

    await login(client, "sam.sales@example.com", "Sales-pass-12345")
    me = (await client.get(f"{API}/auth/me")).json()
    assert me["scope"] == "own"
    assert "crm.lead.create" in me["permissions"]
    assert "crm.quote.approve_rate" not in me["permissions"]

    assert (await client.get(f"{API}/crm/ping")).status_code == 200  # has crm.lead.view
    assert (await client.get(f"{API}/users")).status_code == 403  # no core.user.view
    assert (await client.get(f"{API}/audit-logs")).status_code == 403


async def test_duplicate_email_rejected(client):
    headers = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    await _create_sales_user(client, headers)
    r = await client.post(
        f"{API}/users",
        headers=headers,
        json={"email": "sam.sales@example.com", "full_name": "Dup", "password": "Sales-pass-12345"},
    )
    assert r.status_code == 409


async def test_weak_password_rejected(client):
    headers = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = await client.post(
        f"{API}/users",
        headers=headers,
        json={"email": "weak@example.com", "full_name": "Weak User", "password": "short"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "weak_password"


async def test_deactivating_user_kills_their_session(client, session_factory):
    from httpx import ASGITransport, AsyncClient

    from app.main import app as fastapi_app

    admin_headers = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    user = await _create_sales_user(client, admin_headers)

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as other:
        await login(other, "sam.sales@example.com", "Sales-pass-12345")
        assert (await other.get(f"{API}/auth/me")).status_code == 200

        r = await client.patch(
            f"{API}/users/{user['id']}", headers=admin_headers, json={"is_active": False}
        )
        assert r.status_code == 200
        assert (await other.get(f"{API}/auth/me")).status_code == 401


async def test_cannot_deactivate_last_admin(client):
    headers = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    me = (await client.get(f"{API}/auth/me")).json()
    r = await client.patch(f"{API}/users/{me['user']['id']}", headers=headers, json={"is_active": False})
    assert r.status_code == 409


async def test_audit_log_records_login(client):
    await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = await client.get(f"{API}/audit-logs", params={"action": "auth.login"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
