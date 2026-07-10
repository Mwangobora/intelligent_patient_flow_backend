from __future__ import annotations

from rest_framework import serializers

from apps.queueing.models import QueueEntryEvent


class QueueEntryEventOutputSerializer(serializers.ModelSerializer):
    performed_by_email = serializers.CharField(source="performed_by.email", read_only=True)

    class Meta:
        model = QueueEntryEvent
        fields = [
            "id",
            "queue_entry",
            "event_type",
            "from_status",
            "to_status",
            "performed_by",
            "performed_by_email",
            "reason",
            "occurred_at",
            "created_at",
        ]
