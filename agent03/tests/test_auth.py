from fastapi.testclient import TestClient

from app.database import Membership, Tenant, User
from app.security.passwords import hash_password, verify_password


def test_password_hash_round_trip():
    encoded = hash_password("CorrectHorseBatteryStaple")
    assert verify_password("CorrectHorseBatteryStaple", encoded)
    assert not verify_password("wrong", encoded)
    assert "CorrectHorseBatteryStaple" not in encoded


def test_login_and_me(client: TestClient, token: str):
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["tenant_name"] == "DocFlow Demo"
    assert "tenant_admin" in response.json()["roles"]


def test_bad_login_is_rejected(client: TestClient):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@docflow.local", "password": "WrongPass!"},
    )
    assert response.status_code == 401


def test_multi_tenant_selection(client: TestClient, database):
    with database.session_factory() as session:
        user = session.query(User).filter_by(email="demo@docflow.local").one()
        tenant = Tenant(name="Second Tenant")
        session.add(tenant)
        session.flush()
        session.add(Membership(user_id=user.id, tenant_id=tenant.id, roles="submitter"))
        session.commit()
        tenant_id = tenant.id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@docflow.local", "password": "Demo123!"},
    )
    assert login.status_code == 200
    assert login.json()["requires_tenant_selection"] is True
    selected = client.post(
        "/api/v1/auth/select-tenant",
        json={"selection_token": login.json()["selection_token"], "tenant_id": tenant_id},
    )
    assert selected.status_code == 200
    assert selected.json()["access_token"]


def test_unknown_token_rejected(client: TestClient):
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401

