# Generated for backend-managed display codes.

import uuid

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CodeSequence",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(default=timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=80, unique=True)),
                ("prefix", models.CharField(max_length=20)),
                ("last_number", models.PositiveIntegerField(default=0)),
                ("padding", models.PositiveSmallIntegerField(default=4)),
            ],
            options={
                "db_table": "code_sequences",
                "ordering": ["key"],
            },
        ),
        migrations.AddConstraint(
            model_name="codesequence",
            constraint=models.CheckConstraint(condition=models.Q(("last_number__gte", 0)), name="ck_code_sequences_last_number"),
        ),
        migrations.AddConstraint(
            model_name="codesequence",
            constraint=models.CheckConstraint(condition=models.Q(("padding__gte", 1)), name="ck_code_sequences_padding"),
        ),
    ]
