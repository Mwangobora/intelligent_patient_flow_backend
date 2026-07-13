from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.notifications.models import PatientNotification, UserPushDevice
from apps.notifications.services import create_patient_notification, send_notification
from apps.notifications.services._crypto import build_value_hash


pytestmark = pytest.mark.django_db


def _grant_all_notification_permissions(user, grant_system_permission):
    for code in [
        "notifications_notification.view",
        "notifications_notification.create",
        "notifications_notification.send",
        "notifications_notification.cancel",
        "notifications_device.view",
        "notifications_device.manage",
    ]:
        grant_system_permission(user=user, permission_code=code)


def _notification_payload(patient, **overrides):
    payload = {
        "patient_id": str(patient.id),
        "notification_type": PatientNotification.NotificationType.GENERAL,
        "channel": PatientNotification.Channel.IN_APP,
        "recipient_user_id": str(patient.user_id),
        "body": "Please review your notification.",
    }
    payload.update(overrides)
    return payload


def test_unauthenticated_users_cannot_access_notification_endpoints(api_client):
    response = api_client.get("/api/v1/notifications/")
    assert response.status_code == 401


def test_unauthorized_user_cannot_create_send_or_cancel(authenticated_client, user_factory, patient):
    user = user_factory()
    client = authenticated_client(user)

    create_response = client.post("/api/v1/notifications/", _notification_payload(patient), format="json")
    assert create_response.status_code == 403

    notification = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Unauthorized test",
    )
    assert client.post(f"/api/v1/notifications/{notification.id}/send/").status_code == 403
    assert client.post(f"/api/v1/notifications/{notification.id}/cancel/").status_code == 403


def test_authorized_user_can_create_patient_notification(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/notifications/", _notification_payload(patient, idempotency_key="general-1"), format="json")

    assert response.status_code == 201
    assert response.data["status"] == PatientNotification.Status.PENDING
    assert "body_encrypted" not in response.data
    assert "destination_encrypted" not in response.data


def test_appointment_notification_requires_appointment_to_belong_to_patient(authenticated_client, user_factory, grant_system_permission, patient, other_patient_appointment):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/notifications/",
        _notification_payload(patient, appointment_id=str(other_patient_appointment.id), notification_type=PatientNotification.NotificationType.APPOINTMENT_CONFIRMATION),
        format="json",
    )

    assert response.status_code == 400


def test_queue_notification_requires_queue_entry_to_belong_to_patient(authenticated_client, user_factory, grant_system_permission, patient, other_patient_queue_entry):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post(
        "/api/v1/notifications/",
        _notification_payload(patient, queue_entry_id=str(other_patient_queue_entry.id), notification_type=PatientNotification.NotificationType.QUEUE_CALLED),
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize("channel", [PatientNotification.Channel.SMS, PatientNotification.Channel.EMAIL])
def test_external_notifications_require_destination(authenticated_client, user_factory, grant_system_permission, patient, channel):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/notifications/", _notification_payload(patient, channel=channel, recipient_user_id=None), format="json")

    assert response.status_code == 400


def test_push_notification_requires_recipient_and_destination(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    missing_recipient = client.post(
        "/api/v1/notifications/",
        _notification_payload(patient, channel=PatientNotification.Channel.PUSH, destination="push-target", recipient_user_id=None),
        format="json",
    )
    missing_destination = client.post(
        "/api/v1/notifications/",
        _notification_payload(patient, channel=PatientNotification.Channel.PUSH, destination=None),
        format="json",
    )

    assert missing_recipient.status_code == 400
    assert missing_destination.status_code == 400


def test_in_app_notification_requires_recipient_user(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/notifications/", _notification_payload(patient, recipient_user_id=None), format="json")

    assert response.status_code == 400


def test_recipient_user_must_be_linked_to_patient(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    other_user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/notifications/", _notification_payload(patient, recipient_user_id=str(other_user.id)), format="json")

    assert response.status_code == 400


def test_idempotency_key_prevents_duplicate_notifications(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    payload = _notification_payload(patient, idempotency_key="dup-key")

    first = client.post("/api/v1/notifications/", payload, format="json")
    second = client.post("/api/v1/notifications/", payload, format="json")

    assert first.status_code == 201
    assert second.status_code == 400


def test_notification_content_is_encrypted_and_not_exposed(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    body = "Sensitive care information"

    response = client.post("/api/v1/notifications/", _notification_payload(patient, body=body), format="json")
    notification = PatientNotification.objects.get(pk=response.data["id"])

    assert response.status_code == 201
    assert body not in notification.body_encrypted
    assert "body_encrypted" not in response.data
    assert "destination_encrypted" not in response.data


def test_cancel_notification_sets_status_and_does_not_delete(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    notification = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Cancel me",
    )

    response = client.post(f"/api/v1/notifications/{notification.id}/cancel/", {"reason": "No longer needed"}, format="json")

    notification.refresh_from_db()
    assert response.status_code == 200
    assert notification.status == PatientNotification.Status.CANCELLED
    assert PatientNotification.objects.filter(pk=notification.id).exists()


def test_cancelled_notification_cannot_be_sent(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    notification = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Cancelled",
    )
    notification.status = PatientNotification.Status.CANCELLED
    notification.save(update_fields=["status", "updated_at"])

    response = client.post(f"/api/v1/notifications/{notification.id}/send/")

    assert response.status_code == 400


def test_delivered_notification_cannot_be_marked_failed_and_failed_cannot_be_delivered(patient):
    delivered = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Delivered",
    )
    send_notification(notification_id=delivered.id)
    with pytest.raises(Exception):
        from apps.notifications.services import mark_notification_failed

        mark_notification_failed(notification_id=delivered.id, failure_reason="Nope")

    failed = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.SMS,
        destination="+255769111111",
        body="Failed",
    )
    failed.status = PatientNotification.Status.FAILED
    failed.attempt_count = 1
    failed.last_attempt_at = timezone.now()
    failed.failed_at = timezone.now()
    failed.failure_reason = "Provider error"
    failed.save(update_fields=["status", "attempt_count", "last_attempt_at", "failed_at", "failure_reason", "updated_at"])
    with pytest.raises(Exception):
        from apps.notifications.services import mark_notification_delivered

        mark_notification_delivered(notification_id=failed.id)


def test_mark_read_works_for_in_app_notification(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    notification = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Read me",
    )
    send_notification(notification_id=notification.id)

    response = client.post(f"/api/v1/notifications/{notification.id}/mark-read/", {}, format="json")

    assert response.status_code == 200
    assert response.data["read_at"] is not None


def test_read_at_cannot_be_before_delivered_at(patient):
    notification = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Read timing",
    )
    delivered = send_notification(notification_id=notification.id)
    from apps.notifications.services import mark_notification_read

    with pytest.raises(Exception):
        mark_notification_read(notification_id=delivered.id, read_at=delivered.delivered_at - timedelta(minutes=1))


def test_register_push_device_stores_hash_and_encrypted_token(authenticated_client, user_factory, grant_system_permission, patient_user):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    token = "raw-push-token-secret"

    response = client.post(
        "/api/v1/notifications/push-devices/",
        {"user_id": str(patient_user.id), "platform": UserPushDevice.Platform.WEB, "raw_token": token, "device_name": "Browser"},
        format="json",
    )
    device = UserPushDevice.objects.get(pk=response.data["id"])

    assert response.status_code == 201
    assert device.token_hash == build_value_hash(token)
    assert token not in device.token_encrypted
    assert "token_hash" not in response.data
    assert "token_encrypted" not in response.data


def test_duplicate_push_token_for_same_user_updates_safely(authenticated_client, user_factory, grant_system_permission, patient_user):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    payload = {"user_id": str(patient_user.id), "platform": UserPushDevice.Platform.IOS, "raw_token": "same-token"}

    first = client.post("/api/v1/notifications/push-devices/", payload, format="json")
    second = client.post("/api/v1/notifications/push-devices/", {**payload, "device_name": "Updated"}, format="json")

    assert first.status_code == 201
    assert second.status_code == 201
    assert UserPushDevice.objects.filter(token_hash=build_value_hash("same-token")).count() == 1


def test_revoked_push_device_cannot_receive_notifications(authenticated_client, user_factory, grant_system_permission, patient_user):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    create_response = client.post(
        "/api/v1/notifications/push-devices/",
        {"user_id": str(patient_user.id), "platform": UserPushDevice.Platform.ANDROID, "raw_token": "revoke-token"},
        format="json",
    )

    response = client.post(f"/api/v1/notifications/push-devices/{create_response.data['id']}/revoke/")
    device = UserPushDevice.objects.get(pk=create_response.data["id"])

    assert response.status_code == 200
    assert device.revoked_at is not None
    assert not device.is_active


def test_factory_creates_appointment_confirmation_notification(authenticated_client, user_factory, grant_system_permission, appointment):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/notifications/appointment-confirmation/", {"appointment_id": str(appointment.id)}, format="json")

    assert response.status_code == 201
    assert response.data["notification_type"] == PatientNotification.NotificationType.APPOINTMENT_CONFIRMATION


def test_factory_creates_queue_called_notification(authenticated_client, user_factory, grant_system_permission, queue_entry):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)

    response = client.post("/api/v1/notifications/queue-called/", {"queue_entry_id": str(queue_entry.id)}, format="json")

    assert response.status_code == 201
    assert response.data["notification_type"] == PatientNotification.NotificationType.QUEUE_CALLED


def test_factory_idempotency_prevents_duplicate_reminders(authenticated_client, user_factory, grant_system_permission, appointment):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    payload = {"appointment_id": str(appointment.id), "idempotency_key": "appointment-reminder-1"}

    first = client.post("/api/v1/notifications/appointment-reminder/", payload, format="json")
    second = client.post("/api/v1/notifications/appointment-reminder/", payload, format="json")

    assert first.status_code == 201
    assert second.status_code == 400


def test_delivery_placeholder_does_not_fake_external_provider_success(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    notification = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.SMS,
        destination="+255769111111",
        body="External delivery",
    )

    response = client.post(f"/api/v1/notifications/{notification.id}/send/")
    notification.refresh_from_db()

    assert response.status_code == 400
    assert notification.status == PatientNotification.Status.FAILED
    assert notification.sent_at is None
    assert notification.failed_at is not None


def test_in_app_delivery_can_be_marked_delivered(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    notification = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="In app delivery",
    )

    response = client.post(f"/api/v1/notifications/{notification.id}/send/")

    assert response.status_code == 200
    assert response.data["status"] == PatientNotification.Status.DELIVERED
    assert response.data["delivered_at"] is not None


def test_pending_notification_selector_returns_due_notifications_only(authenticated_client, user_factory, grant_system_permission, patient):
    user = user_factory()
    _grant_all_notification_permissions(user, grant_system_permission)
    client = authenticated_client(user)
    due = create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Due",
        scheduled_for=timezone.now() - timedelta(minutes=1),
    )
    create_patient_notification(
        patient_id=patient.id,
        notification_type=PatientNotification.NotificationType.GENERAL,
        channel=PatientNotification.Channel.IN_APP,
        recipient_user_id=patient.user_id,
        body="Future",
        scheduled_for=timezone.now() + timedelta(hours=1),
    )

    response = client.get("/api/v1/notifications/?scheduled_pending=true")

    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [str(due.id)]
