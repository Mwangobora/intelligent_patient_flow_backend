from __future__ import annotations

from rest_framework import serializers

from apps.queueing.models import QueueTransfer


class QueueTransferInputSerializer(serializers.Serializer):
    destination_queue_id = serializers.UUIDField()
    transfer_reason = serializers.CharField(max_length=250)
    transferred_at = serializers.DateTimeField(required=False, allow_null=True)


class QueueTransferOutputSerializer(serializers.ModelSerializer):
    source_queue = serializers.UUIDField(source="source_queue_entry.queue_id", read_only=True)
    destination_queue = serializers.UUIDField(source="destination_queue_entry.queue_id", read_only=True)
    source_sequence_number = serializers.IntegerField(source="source_queue_entry.sequence_number", read_only=True)
    destination_sequence_number = serializers.IntegerField(source="destination_queue_entry.sequence_number", read_only=True)

    class Meta:
        model = QueueTransfer
        fields = [
            "id",
            "source_queue_entry",
            "source_queue",
            "source_sequence_number",
            "destination_queue_entry",
            "destination_queue",
            "destination_sequence_number",
            "transferred_by",
            "transfer_reason",
            "transferred_at",
            "created_at",
        ]
