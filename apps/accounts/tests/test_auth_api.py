from __future__ import annotations

from django.urls import reverse
from django.conf import settings

import pytest


@pytest.mark.django_db
def test_login_with_email_sets_http_only_cookies(api_client, user_factory):
    user = user_factory(email="email-login@example.com", phone_number=None)

    response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "Password123!"},
        format="json",
    )

    assert response.status_code == 200
    assert settings.AUTH_COOKIE_ACCESS_NAME in response.cookies
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]["httponly"]
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]["samesite"] == settings.AUTH_COOKIE_SAMESITE
    assert response.data["user"]["email"] == user.email
    assert "password" not in response.data["user"]
    assert "is_staff" not in response.data["user"]
    assert "is_superuser" not in response.data["user"]


@pytest.mark.django_db
def test_login_sets_refresh_cookie_if_refresh_exists(api_client, user_factory):
    user = user_factory(email="phone-login@example.com", phone_number="+255700111222")

    response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.phone_number, "password": "Password123!"},
        format="json",
    )

    assert response.status_code == 200
    assert settings.AUTH_COOKIE_REFRESH_NAME in response.cookies
    assert response.cookies[settings.AUTH_COOKIE_REFRESH_NAME]["httponly"]
    assert response.data["user"]["phone_number"] == user.phone_number


@pytest.mark.django_db
def test_login_with_wrong_password_fails(api_client, user_factory):
    user = user_factory(email="wrong-password@example.com")

    response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "WrongPassword123!"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Invalid credentials."


@pytest.mark.django_db
def test_inactive_user_cannot_login(api_client, user_factory):
    user = user_factory(email="inactive-login@example.com")
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])

    response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "Password123!"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["detail"] == "User account is inactive."


@pytest.mark.django_db
def test_refresh_token_endpoint_works(api_client, user_factory):
    user = user_factory(email="refresh@example.com")

    login_response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "Password123!"},
        format="json",
    )
    refresh = login_response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    response = api_client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json")

    assert response.status_code == 200
    assert response.data["detail"] == "Session refreshed."
    assert settings.AUTH_COOKIE_ACCESS_NAME in response.cookies


@pytest.mark.django_db
def test_logout_clears_cookies(api_client, user_factory):
    user = user_factory(email="logout@example.com")

    login_response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "Password123!"},
        format="json",
    )
    api_client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = login_response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    api_client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = login_response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    response = api_client.post(reverse("auth-logout"), format="json")

    assert response.status_code == 204
    assert response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value == ""
    assert response.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value == ""


@pytest.mark.django_db
def test_auth_me_requires_authentication(api_client):
    response = api_client.get(reverse("auth-me"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_authenticated_user_can_access_auth_me_using_cookie(api_client, user_factory):
    user = user_factory(email="me@example.com", middle_name="Middle")
    login_response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "Password123!"},
        format="json",
    )
    api_client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = login_response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value

    response = api_client.get(reverse("auth-me"))

    assert response.status_code == 200
    assert response.data["email"] == user.email
    assert response.data["middle_name"] == "Middle"
    assert "password" not in response.data
    assert "is_staff" not in response.data
    assert "is_superuser" not in response.data


@pytest.mark.django_db
def test_authenticated_user_can_update_own_names(authenticated_client, user_factory):
    user = user_factory(email="update-me@example.com")
    client = authenticated_client(user)

    response = client.patch(
        reverse("auth-me"),
        {
            "first_name": "Updated",
            "middle_name": "Changed",
            "last_name": "Name",
        },
        format="json",
    )

    user.refresh_from_db()

    assert response.status_code == 200
    assert user.first_name == "Updated"
    assert user.middle_name == "Changed"
    assert user.last_name == "Name"


@pytest.mark.django_db
def test_user_cannot_update_is_staff_is_superuser_or_is_active_through_auth_me(authenticated_client, user_factory):
    user = user_factory(email="guarded-me@example.com")
    client = authenticated_client(user)

    response = client.patch(
        reverse("auth-me"),
        {
            "first_name": "Allowed",
            "is_staff": True,
            "is_superuser": True,
            "is_active": False,
        },
        format="json",
    )

    user.refresh_from_db()

    assert response.status_code == 200
    assert user.first_name == "Allowed"
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_active is True


@pytest.mark.django_db
def test_change_password_succeeds_and_old_password_stops_working(api_client, authenticated_client, user_factory):
    user = user_factory(email="password-change@example.com")
    client = authenticated_client(user)

    change_response = client.post(
        reverse("auth-change-password"),
        {"old_password": "Password123!", "new_password": "NewPassword123!"},
        format="json",
    )
    old_login_response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "Password123!"},
        format="json",
    )
    new_login_response = api_client.post(
        reverse("auth-login"),
        {"email_or_phone": user.email, "password": "NewPassword123!"},
        format="json",
    )

    assert change_response.status_code == 204
    assert old_login_response.status_code == 400
    assert new_login_response.status_code == 200


@pytest.mark.django_db
def test_change_password_fails_with_wrong_old_password(authenticated_client, user_factory):
    user = user_factory(email="wrong-old-password@example.com")
    client = authenticated_client(user)

    response = client.post(
        reverse("auth-change-password"),
        {"old_password": "WrongPassword123!", "new_password": "NewPassword123!"},
        format="json",
    )

    assert response.status_code == 400
    assert "Old password is incorrect." in str(response.data)
