# 🔧 Troubleshooting Guide

> Common issues and solutions for the Databricks Postgres Streamlit Apps project.

---

## Table of Contents

1. [Connection Issues](#connection-issues)
2. [Streamlit Cloud Deployment Issues](#streamlit-cloud-deployment-issues)
3. [Sync Issues](#sync-issues)
4. [Streamlit App Issues](#streamlit-app-issues)
5. [Databricks App Deployment](#databricks-app-deployment)
6. [Git & GitHub Issues](#git--github-issues)
7. [CI/CD Pipeline Issues](#cicd-pipeline-issues)

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

## Streamlit Cloud Deployment Issues

### Problem: "Endpoint name expects 'projects/{project_id}/branches/{branch_id}/endpoints/{endpoint_id}' format"

**Cause**: Missing `branches/{branch}` segment in the SDK endpoint path.

**Symptom**: App shows "Databricks SDK connection failed: Endpoint name expects ..." in the connection status box.

**Solution**: The app now correctly includes the branch in the endpoint path. Ensure you have `LAKEBASE_BRANCH` in your Streamlit secrets:

```toml
LAKEBASE_BRANCH = "production"
```

If the secret is missing, the app defaults to `"production"`.

**Root Cause**: The Databricks SDK requires the full hierarchical path: `projects/{project}/branches/{branch}/endpoints/{endpoint}`. Earlier versions omitted the branch segment.

**Fixed in**: Commit `82ed057` (September 20, 2026)

---

### Problem: "psycopg.errors.UndefinedTable: relation 'public.synced_well_production' does not exist"

**Cause**: App looked for table in `public` schema but Reverse ETL created it in `oil_gas_ops` schema.

**Symptom**: Dashboard loads but shows "No data found" or an UndefinedTable error.

**Solution**: The app now uses `SCHEMA_NAME = "oil_gas_ops"` to match the actual Postgres schema.

**How to verify your schema**:

```sql
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_name = 'synced_well_production';
```

**Root Cause**: Reverse ETL creates the Postgres table in a schema matching the Unity Catalog schema name (e.g., `workspace.oil_gas_ops.synced_well_production` → Postgres `oil_gas_ops.synced_well_production`), NOT in the `public` schema.

**Fixed in**: Commit `95ce17b` (September 20, 2026)

---

### Problem: "current transaction is aborted, commands ignored until end of transaction block"

**Cause**: A database error (e.g., duplicate key, constraint violation) aborted the transaction, and subsequent commands were ignored until rollback.

**Symptom**: After attempting to add a well (or any write operation), all subsequent operations show this error message.

**Solution**: The app now automatically rolls back failed transactions. The `execute_query()` function includes:

```python
try:
    cur.execute(query, params)
    conn.commit()
except Exception as e:
    conn.rollback()
    raise Exception(f"Database error: {str(e)}")
```

**Root Cause**: PostgreSQL aborts transactions on errors. Without explicit rollback, the connection stays in an aborted state and rejects all subsequent commands.

**Fixed in**: Commit `5e00d62` (September 20, 2026)

**Common triggers**:
* Duplicate primary key (e.g., trying to insert well_id=26 when it already exists)
* NULL values in NOT NULL columns
* Data type mismatches
* Check constraint violations

---

### Problem: App shows secrets error or KeyError

**Cause**: Using `st.secrets["KEY"]` instead of `st.secrets.get("KEY")` causes KeyError when a secret is missing.

**Symptom**: App crashes with `KeyError: 'DATABRICKS_HOST'` or similar.

**Solution**: App now uses `st.secrets.get(key)` with fallback to environment variables:

```python
def _get_secret(key, fallback_env=None):
    try:
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(fallback_env or key, "")
```

**Root Cause**: `st.secrets[key]` raises KeyError on missing keys; `.get(key)` returns None safely.

**Fixed in**: Commit `f7f6f28` (September 20, 2026)

---

### Problem: App shows "No data found" but UC table has data

**Cause**: Reverse ETL sync hasn't run yet, or sync is in triggered mode and needs manual execution.

**Solution**:

1. Check if the UC synced table has data:
   ```sql
   SELECT COUNT(*) FROM workspace.oil_gas_ops.synced_well_production;
   ```

2. Check if the Postgres table has data (using Lakebase SQL):
   ```sql
   SELECT COUNT(*) FROM oil_gas_ops.synced_well_production;
   ```

3. If UC synced table is empty, trigger a sync update from Databricks:
   - Go to your synced table in Catalog Explorer
   - Click "Update" to manually trigger the sync

4. Wait 10-30 seconds for the sync pipeline to complete

**Note**: Triggered syncs do NOT run automatically — they only run when you click "Update" or via API.

---

### Problem: PAT expired (after 90 days)

**Cause**: Databricks Personal Access Tokens have a maximum 90-day lifetime.

**Symptom**: App shows authentication errors like "Invalid token" or "401 Unauthorized".

**Solution**:

1. Generate a new PAT:
   - Go to Databricks Settings → Developer → Access Tokens
   - Click "Generate new token"
   - Set lifetime: 90 days (maximum)
   - Copy the new token

2. Update Streamlit Cloud secrets:
   - Go to your app → Settings → Secrets
   - Replace `DATABRICKS_TOKEN` with the new token
   - Click Save

3. App will auto-restart with the new token

**Prevention**: Set a calendar reminder 85 days after generating the PAT to regenerate before expiration.

---

### Problem: Cold start takes 15-30 seconds

**Cause**: Streamlit Cloud free tier apps sleep after inactivity. The Lakebase endpoint also scales to zero.

**Symptom**: First page load after inactivity shows a "Your app is waking up" message.

**Solution**: This is normal behavior for the free tier. No action needed.

**Why it happens**:
1. Streamlit app wakes up (~5-10 seconds)
2. Lakebase Postgres endpoint wakes up (~5-10 seconds)
3. App establishes connection and queries data (~1-2 seconds)

**Mitigation**: Consider upgrading to Streamlit Cloud paid tier if cold starts are unacceptable, or use Databricks Apps (always-on, no cold starts).

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

---

## CI/CD Pipeline Issues

### Problem: CI fails on "Validate app.yaml structure"

**Cause**: YAML parsing issue in GitHub Actions environment.

**Solution**:
1. Verify `app/app.yaml` exists in the repo
2. Check YAML syntax locally: `python -c "import yaml; yaml.safe_load(open('app/app.yaml'))"`
3. Ensure no tabs are used (YAML requires spaces)
4. Check that the heredoc Python block in `ci-cd.yml` is properly indented

---

### Problem: CI fails on "Check for hardcoded secrets"

**Cause**: The secret scanner found a pattern matching `(password|token|secret) = "value"`.

**Solution**:
1. Review the CI log for the flagged file and line number
2. Replace hardcoded values with environment variable references:
   ```python
   # BAD
   password = "my-secret-token-12345"
   
   # GOOD
   password = os.environ.get("PASSWORD", "")
   ```
3. If it is a false positive (e.g., a variable name), restructure to avoid the pattern

---

### Problem: CD deployment skipped with "secrets not set"

**Cause**: GitHub repository secrets (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_APP_NAME`) are not configured.

**Solution**:
1. Go to GitHub > Settings > Secrets and variables > Actions
2. Add the three required secrets
3. Create GitHub Environments: `dev` and `main` (production)
4. Re-run the workflow or merge a new PR

---

### Problem: GitHub Actions push fails with "refusing to allow an OAuth App to create or update workflow"

**Cause**: The GitHub token/credential lacks `workflow` scope.

**Solution**:
1. Update your GitHub Personal Access Token to include the `workflow` scope
2. In Databricks: Settings > Git > Credentials, update the credential
3. Or use a different credential that has the `workflow` scope

---

### Problem: `flake8` fails with syntax errors

**Cause**: Python syntax issues in `app/app.py`.

**Solution**:
1. Run flake8 locally: `flake8 app/ --count --select=E9,F63,F7,F82 --show-source --statistics`
2. Fix any syntax errors reported
3. Push the fix to re-trigger CI