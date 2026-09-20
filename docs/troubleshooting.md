# 🔧 Troubleshooting Guide

> Common issues and solutions for the Databricks Postgres Streamlit Apps project.

---

## Table of Contents

1. [Connection Issues](#connection-issues)
2. [Sync Issues](#sync-issues)
3. [Streamlit App Issues](#streamlit-app-issues)
4. [Databricks App Deployment](#databricks-app-deployment)
5. [Git & GitHub Issues](#git--github-issues)

---

## Connection Issues

### Problem: `connection refused` or `could not connect to server`

**Cause**: Endpoint is scaled to zero (idle timeout) or not yet ready.

**Solution**: 
- Wait ~100ms for the endpoint to wake up.
- Implement retry logic in your app:
```python
import time
for attempt in range(5):
    try:
        conn = psycopg.connect(host=host, ...)
        break
    except Exception:
        time.sleep(1)
```

---

### Problem: `authentication failed` or `password authentication failed`

**Cause**: Using the workspace OAuth token instead of a Lakebase-scoped token.

**Solution**: Always use `generate_database_credential()`:
```python
# WRONG - workspace token is rejected
password = w.config.oauth_token().access_token

# CORRECT - Lakebase-scoped token
password = w.postgres.generate_database_credential(
    endpoint="projects/.../endpoints/primary"
).token
```

---

### Problem: `SSL required` or `SSL is not enabled on the server`

**Cause**: Missing `sslmode=require` in connection string.

**Solution**: Always use SSL:
```python
conn = psycopg.connect(host=host, sslmode="require", ...)
```

---

### Problem: Token expired during long-running query

**Cause**: OAuth tokens expire after 1 hour.

**Solution**: Use connection pooling with token rotation:
```python
# Set pool_recycle to 2700 (45 min) to recycle before 1-hour expiry
engine = create_engine(url, pool_recycle=2700, pool_pre_ping=True)
```

---

### Problem: DNS resolution fails (macOS)

**Cause**: Python's `socket.getaddrinfo()` can fail with long hostnames on macOS.

**Solution**: Use `dig` to resolve the IP and pass via `hostaddr`:
```python
import socket
ip = socket.gethostbyname(host)
conn = psycopg.connect(host=host, hostaddr=ip, sslmode="require", ...)
```

---

## Sync Issues

### Problem: Sync table shows `SYNCED_TABLE_PROVISIONING_PIPELINE_RESOURCES`

**Cause**: The sync pipeline is still being provisioned.

**Solution**: Wait a few minutes and check status:
```python
st = w.postgres.get_synced_table(name="synced_tables/workspace.oil_gas_ops.synced_well_production")
print(st.status.detailed_state)
```

---

### Problem: Sync not picking up changes

**Cause**: CDF is not enabled on the source table, or the sync mode is Snapshot.

**Solution**: 
1. Verify CDF is enabled:
```sql
SHOW TBLPROPERTIES workspace.oil_gas_ops.well_production;
```
2. If not enabled, enable it:
```sql
ALTER TABLE workspace.oil_gas_ops.well_production
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
```
3. Check sync mode is Triggered or Continuous (not Snapshot).

---

### Problem: `permission denied for schema`

**Cause**: The app's Service Principal doesn't have access to the schema.

**Solution**: 
- For Databricks Apps: Deploy the app FIRST so the SP creates/owns the schema.
- For existing schemas: Grant access:
```sql
GRANT USAGE ON SCHEMA public TO "your-app-sp";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "your-app-sp";
```

---

## Streamlit App Issues

### Problem: `No module named 'psycopg'`

**Solution**: Install psycopg3:
```bash
pip install "psycopg[binary]"
```
Or use psycopg2 as fallback:
```bash
pip install psycopg2-binary
```

---

### Problem: `No data found` in the dashboard

**Cause**: The Reverse ETL sync hasn't completed yet.

**Solution**:
1. Check sync status in the notebook or Databricks UI
2. Wait for the pipeline to complete the initial sync
3. Verify data in Postgres:
```python
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM public.synced_well_production")
print(cur.fetchone())
```

---

### Problem: Charts not displaying

**Solution**: Ensure plotly is installed:
```bash
pip install plotly>=5.18.0
```

---

## Databricks App Deployment

### Problem: App fails to start

**Solution**: 
1. Check `app.yaml` configuration
2. Verify the Lakebase project name matches
3. Check the app logs:
```bash
databricks apps logs <app-name>
```

---

### Problem: App can't connect to Postgres

**Solution**: 
1. Deploy the app first (before running locally)
2. Verify the Service Principal has database access
3. Check that the schema exists and is accessible

---

## Git & GitHub Issues

### Problem: `Authentication failed` when pushing

**Solution**: Use the correct Git credential:
- If using `runGit`, specify `gitCredentialId: "640659877749455"`
- If using CLI, ensure your GitHub token has repo access

---

### Problem: `Could not read remote repository`

**Solution**: 
1. Verify the repo URL is correct
2. Check that the repo exists on GitHub
3. Verify your credential has access to the repo

---

## Getting Help

If you encounter an issue not listed here:
1. Check the [Lakebase Postgres documentation](https://docs.databricks.com/aws/en/oltp/)
2. Review the Databricks SDK logs
3. Contact the project maintainer