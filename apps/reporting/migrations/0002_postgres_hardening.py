from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("facilities", "0002_postgres_hardening"),
        ("reporting", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER trg_report_exports_validate_scope
            BEFORE INSERT OR UPDATE OF organization_id, facility_id
            ON report_exports
            FOR EACH ROW EXECUTE FUNCTION validate_org_facility_pair();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_report_exports_validate_scope ON report_exports;
            """,
        ),
    ]
