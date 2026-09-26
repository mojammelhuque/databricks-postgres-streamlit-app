# PostgreSQL settings and maintenance

Central record for the Databricks Lakebase PostgreSQL connection used by the Streamlit application. Record future PostgreSQL setting changes and recovery work here.

## Recorded settings

Last confirmed: 2026-09-25. Values below come from the Lakebase screenshot and the successful recovery reported by the user; they are not a live configuration export.

| Setting | Recorded value |
| --- | --- |
| Service | Databricks Lakebase PostgreSQL |
| Project display name | Databricks Postgres Streamlit |
| Project ID | `databricks-postgres-streamlit` |
| Branch | `production` (default) |
| Compute / endpoint name | `primary` |
| Endpoint resource name | `projects/databricks-postgres-streamlit/branches/production/endpoints/primary` |
| PostgreSQL port | `5432` |
| Compute size | `1 CU` (shown before recovery) |
| High availability (HA) | Disabled (shown before recovery; separate from endpoint enablement) |
| Endpoint disabled status | `False` after recovery |
| Application connection | Working, confirmed by the user after recovery |
| Workspace URL | `https://dbc-050f2fd4-a450.cloud.databricks.com` (repository README; live value not checked) |
| Database hostname | `ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com` (repository README; live value not checked) |
| Database name | `databricks_postgres` (app default; live value not checked) |
| Database role | Configured through `LAKEBASE_PG_USER`; live value not recorded |
| Authentication method | Streamlit Cloud SDK token generation; workspace credentials stored in Streamlit secrets |
| SSL configuration | `sslmode="require"` in the SDK connection path |
| Scale-to-zero / inactivity timeout | Not yet recorded |

Keep passwords, tokens, and connection strings containing credentials out of this document. Record non-secret settings and references to the application's secret configuration instead.

## Configuration references

- [Application connection code](../app/app.py): connection selection and SDK token generation; the connection resource has a 2,700-second (45-minute) cache TTL.
- [Streamlit Cloud deployment](streamlit_cloud_deployment.md): secret setup and deployment steps.
- [Security](security.md): credential management.

The SDK path reads `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `LAKEBASE_PG_HOST`, `LAKEBASE_PG_USER`, `LAKEBASE_PG_DB`, `LAKEBASE_PG_PORT`, `LAKEBASE_PROJECT`, and `LAKEBASE_BRANCH`. Keep live credential values in Streamlit secrets.

## Incident: disabled endpoint (2026-09-25)

The Streamlit connection failed with:

```text
Databricks SDK connection failed: connection failed:
connection to server at "18.97.131.216", port 5432 failed:
ERROR: The endpoint has been disabled. Enable it using the API and retry.
Multiple connection attempts failed.
```

The Lakebase branch page showed the `primary` compute as `SUSPENDED`. The server error identified a disabled endpoint; the screenshot alone does not distinguish endpoint disablement from ordinary suspension. The reason it was disabled was not established.

The IP above is historical error evidence, not a configured database hostname. Use the hostname supplied by Lakebase connection details.

### Recovery procedure

Run this in a Databricks Python notebook, or a Python environment with the Databricks SDK and workspace authentication configured. The authenticated identity must have permission to update the endpoint.

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import (
    Endpoint, EndpointSpec, EndpointType, FieldMask,
)

w = WorkspaceClient()
name = "projects/databricks-postgres-streamlit/branches/production/endpoints/primary"

w.postgres.update_endpoint(
    name=name,
    endpoint=Endpoint(
        name=name,
        spec=EndpointSpec(
            endpoint_type=EndpointType.ENDPOINT_TYPE_READ_WRITE,
            disabled=False,
        ),
    ),
    update_mask=FieldMask(field_mask=["spec.disabled"]),
).wait()

print("Disabled:", w.postgres.get_endpoint(name=name).status.disabled)
```

The update mask limits the change to `spec.disabled`. It does not change compute size, HA, or scale-to-zero settings.

### Verification and outcome

1. The command returned `Disabled: False`.
2. The user retried the application connection and confirmed it was working.

Allow the compute to finish restarting before retrying. A disabled compute requires API re-enablement; repeated connection attempts do not wake it. The UI's `HA Disabled` label concerns high availability and is unrelated to this enablement setting.

For a later read-only status check:

```python
endpoint = w.postgres.get_endpoint(name=name)
print("Disabled:", endpoint.status.disabled)
print("State:", endpoint.status.current_state)
```

If the connection still fails after enablement and restart, capture the new error before choosing another fix.

Reference: [Databricks: disable or enable a compute](https://docs.databricks.com/aws/en/oltp/projects/manage-computes#disable-or-enable-a-compute).

## Maintenance history

| Date | Change | Validation |
| --- | --- | --- |
| 2026-09-25 | Re-enabled the production `primary` endpoint through the SDK by setting `spec.disabled=False`. | `Disabled: False`; user confirmed the application connection worked. |

For future changes, update the settings table and append a history entry with the date, affected setting, previous and new values when known, reason, and verification result.
