from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

API = "/api/v1"


async def test_login_and_me(client):
    await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = await client.get(f"{API}/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["scope"] == "all"
    assert "crm.quote.approve_rate" in body["permissions"]


async def test_me_requires_login(client):
    r = await client.get(f"{API}/auth/me")
    assert r.status_code == 401
    assert r.json()["code"] == "not_authenticated"


async def test_wrong_password_is_generic(client):
    r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "nope-nope-1"})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"
    r = await client.post(f"{API}/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-1"})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


async def test_lockout_after_repeated_failures(client):
    for _ in range(5):
        await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-pass-1"})
    r = await client.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 429
    assert r.json()["code"] == "account_locked"


async def test_csrf_required_for_writes(client):
    await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = await client.post(f"{API}/auth/logout")  # no X-CSRF-Token header
    assert r.status_code == 403
    assert r.json()["code"] == "csrf_failed"


async def test_logout_invalidates_session(client):
    headers = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert (await client.post(f"{API}/auth/logout", headers=headers)).status_code == 204
    assert (await client.get(f"{API}/auth/me")).status_code == 401


async def test_change_password(client):
    headers = await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    new_pw = "Another-pass-98765"
    r = await client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": ADMIN_PASSWORD, "new_password": new_pw},
    )
    assert r.status_code == 204
    await client.post(f"{API}/auth/logout", headers=headers)
    await login(client, ADMIN_EMAIL, new_pw)
