from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
        ("facilities", "0002_postgres_hardening"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TRIGGER trg_audit_logs_validate_scope
            BEFORE INSERT OR UPDATE OF organization_id, facility_id
            ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION validate_org_facility_pair();

            CREATE TRIGGER trg_audit_logs_append_only
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_history_mutation();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;
            DROP TRIGGER IF EXISTS trg_audit_logs_validate_scope ON audit_logs;
            """,
        ),
    ]
