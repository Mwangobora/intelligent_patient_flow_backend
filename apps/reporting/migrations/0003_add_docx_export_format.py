from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("reporting", "0002_postgres_hardening"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reportexport",
            name="export_format",
            field=models.CharField(choices=[("csv", "CSV"), ("xlsx", "XLSX"), ("pdf", "PDF"), ("docx", "DOCX")], max_length=10),
        ),
        migrations.RemoveConstraint(
            model_name="reportexport",
            name="ck_report_exports_format",
        ),
        migrations.AddConstraint(
            model_name="reportexport",
            constraint=models.CheckConstraint(condition=Q(export_format__in=["csv", "xlsx", "pdf", "docx"]), name="ck_report_exports_format"),
        ),
    ]
