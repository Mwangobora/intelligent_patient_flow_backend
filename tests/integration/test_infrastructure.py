import pytest
from django.conf import settings
from redis import Redis
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


def test_settings_loading():
    assert settings.ROOT_URLCONF == "config.urls"
    assert "apps.accounts" in settings.INSTALLED_APPS


@pytest.mark.django_db
def test_ready_health_endpoint(api_client, monkeypatch):
    monkeypatch.setattr(Redis, "ping", lambda self: True)
    response = api_client.get("/health/ready/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
