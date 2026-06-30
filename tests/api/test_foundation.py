import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_api_root(api_client):
    response = api_client.get("/api/v1/")
    assert response.status_code == 200
    assert response.json()["name"] == "intelligent_patient_flow_backend"


@pytest.mark.django_db
def test_live_health_endpoint(api_client):
    response = api_client.get("/health/live/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
