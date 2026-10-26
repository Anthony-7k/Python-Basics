from fastapi.testclient import TestClient

from app.database import Membership, Tenant, User
from app.security.passwords import hash_password


def test_cross_tenant_case_is_hidden(client: TestClient, auth, database):
    created = client.post("/api/v1/cases", headers=auth, json={"title": "private", "description": ""})
    case_id = created.json()["id"]
    with database.session_factory() as session:
        tenant = Tenant(name="Isolated Corp")
        user = User(email="other@example.com", display_name="Other", password_hash=hash_password("Other123!"))
        session.add_all([tenant, user])
        session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user.id, roles="submitter"))
        session.commit()
    login = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "Other123!"})
    other_auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"/api/v1/cases/{case_id}", headers=other_auth).status_code == 404
    assert all(item["id"] != case_id for item in client.get("/api/v1/cases", headers=other_auth).json())

