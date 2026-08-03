import os

os.environ.setdefault("WILDLIFE_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WILDLIFE_JWT_SECRET", "test-secret")
os.environ.setdefault("WILDLIFE_BOOTSTRAP_ADMIN_PASSWORD", "admin123")
os.environ.setdefault("WILDLIFE_DETECTOR_BACKEND", "mock")
os.environ.setdefault("WILDLIFE_CLASSIFIER_BACKEND", "mock")
os.environ.setdefault("WILDLIFE_REFERENCE_RETRIEVAL_BACKEND", "histogram")

from fastapi.testclient import TestClient

from app.auth import hash_password, verify_password
from app.main import app

client = TestClient(app)


def login(username: str = "admin", password: str = "admin123") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong", first)


def test_login_me_and_feature_flags() -> None:
    headers = login()
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["roles"] == ["system_admin"]
    features = client.get("/api/v1/features", headers=headers)
    assert features.status_code == 200
    assert features.json()["plant_recognition"] is False


def test_field_report_automatically_enters_review_queue() -> None:
    admin_headers = login()
    created = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={"username": "patrol-test", "display_name": "巡护测试员", "password": "patrol-password", "roles": ["patrol_user"]},
    )
    assert created.status_code in {201, 409}
    patrol_headers = login("patrol-test", "patrol-password")
    report = client.post(
        "/api/v1/field-reports",
        headers=patrol_headers,
        json={"species_name": "中华穿山甲", "latitude": 23.1, "longitude": 108.3, "location_text": "测试监测点", "notes": "单只经过"},
    )
    assert report.status_code == 201, report.text
    reviews = client.get("/api/v1/admin/reviews?review_status=pending", headers=admin_headers)
    assert reviews.status_code == 200
    assert any(item["report_id"] == report.json()["id"] for item in reviews.json())


def test_role_enforcement_and_coordinate_validation() -> None:
    patrol_headers = login("patrol-test", "patrol-password")
    assert client.get("/api/v1/admin/users", headers=patrol_headers).status_code == 403
    invalid = client.post("/api/v1/field-reports", headers=patrol_headers, json={"species_name": "测试", "latitude": 100})
    assert invalid.status_code == 422
