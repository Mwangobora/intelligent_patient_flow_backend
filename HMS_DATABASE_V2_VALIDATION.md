# HMS Database V2 Validation

## Validation Summary

- Static table count check: passed.
- Duplicate table-name check: passed.
- Foreign-key referenced table existence check: passed.
- Transaction wrapper check: passed.
- Live PostgreSQL execution: not completed in this shell because Docker access is blocked.

## Static Results

```text
table_count= 125
duplicate_tables= none
missing_references= none
triggers= 75
functions= 47
indexes= 216
begin_commit= 1 1
```

## Requested Count

- Original business tables: 50
- New HMS tables requested/added: 75
- Final business tables: 125

## Live Execution Blocker

The requested PostgreSQL validation could not be executed from this environment.

Docker Desktop socket error:

```text
failed to connect to the docker API at unix:///home/francis/.docker/desktop/docker.sock
```

System Docker socket error:

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

Local `psql` is also unavailable in this shell, so the SQL was validated statically only.

## Command To Run When Docker Access Is Available

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 < intelligent_patient_flow_database.sql
```

If the Compose service name is different, first run:

```bash
docker compose ps
```

Then replace `postgres` with the actual database service name.

## Validation Caveat

Static validation confirms table counts and referenced table names, but it does not replace executing the full SQL in PostgreSQL 15+. PostgreSQL execution should still be run before treating this schema as deployment-ready.

