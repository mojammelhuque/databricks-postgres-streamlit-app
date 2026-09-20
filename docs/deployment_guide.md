# 🚀 Deployment Guide

> Step-by-step instructions for deploying the Oil & Gas Streamlit app to Databricks Apps and local/RStudio environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Option A: Databricks Apps (Hosted)](#option-a-databricks-apps-hosted)
3. [Option B: Local Development](#option-b-local-development)
4. [Option C: RStudio / Posit Workbench](#option-c-rstudio--posit-workbench)
5. [CI/CD Automated Deployment](#cicd-automated-deployment)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Rollback Procedure](#rollback-procedure)

---

## Prerequisites

### Required Resources

| Resource | Value | Status |
|----------|-------|--------|
| Lakebase Project | `databricks-postgres-streamlit` | Created |
| Lakebase Branch | `production` | Ready |
| Lakebase Endpoint | `primary` (read-write, scale-to-zero) | Active |
| Lakebase Database | `databricks_postgres` | Created |
| UC Source Table | `workspace.oil_gas_ops.well_production` | Created (25 rows, CDF enabled) |
| Synced Table | `workspace.oil_gas_ops.synced_well_production` | Synced (Triggered mode) |
| Sync Pipeline ID | `a41bf65e-3ca8-4522-aebf-e196234fd973` | IDLE |

### Required Tools

- **Databricks CLI** (for hosted deployment)
- **Python 3.10+** (for local development)
- **Git** (for CI/CD and version control)
- **Databricks SDK for Python** >= 0.118.0 (for token generation)

---

## Option A: Databricks Apps (Hosted)

### Overview

Databricks Apps provides a fully managed hosting environment with automatic credential injection, SSL/TLS, and OAuth token rotation.

### Step 1: Verify Lakebase Postgres is Running

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Check project status
project = w.postgres.get_project(
    name="projects/databricks-postgres-streamlit"
)
print(f"Project status: {project.status}")

# Check endpoint status
endpoint = w.postgres.get_endpoint(
    name="projects/databricks-postgres-streamlit/endpoints/primary"
)
print(f"Endpoint status: {endpoint.status}")
```

### Step 2: Verify Sync is Complete

```python
# Check synced table status
synced = w.postgres.get_synced_table(
    name="synced_tables/workspace.oil_gas_ops.synced_well_production"
)
print(f"Sync status: {synced.status.detailed_state}")
```

### Step 3: Deploy the App

```bash
# Using Databricks CLI
APP_NAME="oil-gas-streamlit-app"

# Check if app already exists
if databricks apps get "$APP_NAME" 2>/dev/null; then
    echo "App exists, deploying update..."
    databricks apps deploy "$APP_NAME" --source-path ./app
else
    echo "Creating new app..."
    databricks apps create "$APP_NAME" --source-path ./app
fi
```

### Step 4: Verify Deployment

```bash
# Check app status
databricks apps get "$APP_NAME"

# View app logs
databricks apps logs "$APP_NAME"

# Access the app
# URL: https://<workspace-url>/apps/<app-name>
```

### How Auto-Configuration Works

The `app/app.yaml` file configures the Lakebase connection:

```yaml
lakebase:
  postgres:
    project: databricks-postgres-streamlit
    branch: production
    database: databricks_postgres
```

Databricks automatically injects these environment variables at runtime:

| Variable | Description |
|----------|-------------|
| `DATABRICKS_LAKEBASE_PG_HOST` | Postgres endpoint URL |
| `DATABRICKS_LAKEBASE_PG_PORT` | Port (default: 5432) |
| `DATABRICKS_LAKEBASE_PG_USER` | Your Databricks identity |
| `DATABRICKS_LAKEBASE_PG_PASSWORD` | OAuth token (rotates hourly) |
| `DATABRICKS_LAKEBASE_PG_DATABASE` | Database name |

**No manual credential management required.**

---

## Option B: Local Development

### Step 1: Clone the Repository

```bash
git clone https://github.com/mojammelhuque/databricks-postgres-streamlit-app.git
cd databricks-postgres-streamlit-app
```

### Step 2: Set Up Python Environment

```bash
cd app/
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Create a `.env` file in the `app/` directory (git-ignored):

```bash
# .env file
LAKEBASE_PG_HOST=ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com
LAKEBASE_PG_PORT=5432
LAKEBASE_PG_DB=databricks_postgres
LAKEBASE_PG_USER=your-email@company.com
LAKEBASE_PG_PASSWORD=your-oauth-token
```

Alternatively, use a full connection URL:

```bash
LAKEBASE_PG_URL="postgresql://user:password@host:5432/db?sslmode=require"
```

### Step 4: Generate OAuth Token (if needed)

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
cred = w.postgres.generate_database_credential(
    endpoint="projects/databricks-postgres-streamlit/endpoints/primary"
)
print(f"Token: {cred.token}")
print(f"Expires: {cred.expiry_time}")
```

### Step 5: Run the App

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

---

## Option C: RStudio / Posit Workbench

### Step 1: Connect to RStudio

```bash
# SSH into your RStudio server
ssh your-user@rstudio-server
```

### Step 2: Set Up Environment

```bash
cd /path/to/databricks-postgres-streamlit-apps/app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Connection

```bash
# Set environment variables in your shell profile (~/.bashrc or ~/.zshrc)
export LAKEBASE_PG_HOST=ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com
export LAKEBASE_PG_PORT=5432
export LAKEBASE_PG_DB=databricks_postgres
export LAKEBASE_PG_USER=your-email@company.com
export LAKEBASE_PG_PASSWORD=your-oauth-token
```

### Step 4: Run on a Specific Port

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### Step 5: Access the App

Open in browser: `http://<rstudio-server>:8501`

---

## CI/CD Automated Deployment

### Overview

The CI/CD pipeline (`.github/workflows/ci-cd.yml`) automates deployment when a PR is merged from `dev` to `main`.

### Required GitHub Secrets

| Secret Name | Description | Example |
|-------------|-------------|--------|
| `DATABRICKS_HOST` | Your Databricks workspace URL | `https://dbc-050f2fd4-a450.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | Databricks personal access token | `dapi1234...` |
| `DATABRICKS_APP_NAME` | Name of the Databricks App | `oil-gas-streamlit-app` |

### GitHub Environments

| Environment | Purpose | Protection |
|-------------|---------|-----------|
| `dev` | Development/testing | None (optional) |
| `main` (production) | Production deployment | Required: manual approval (recommended) |

### Deployment Flow

```
1. Developer pushes to `dev` branch
2. CI pipeline runs (lint, validate, secret scan)
3. Developer opens PR: dev -> main
4. CI pipeline runs again on the PR
5. Reviewer approves and merges the PR
6. CD pipeline triggers automatically
7. Databricks CLI deploys the app
8. App is live on Databricks Apps
```

### Manual Trigger

You can manually trigger the CI/CD pipeline:

1. Go to GitHub > Actions tab
2. Select "CI/CD Pipeline"
3. Click "Run workflow"
4. Choose environment: `production` or `staging`
5. Click "Run workflow"

---

## Post-Deployment Verification

### 1. Check App Status

```bash
databricks apps get oil-gas-streamlit-app
```

Expected output: `status: RUNNING` or `status: READY`

### 2. Check App Logs

```bash
databricks apps logs oil-gas-streamlit-app
```

Look for:
- `Streamlit app started successfully`
- `Connected to <host>/<database>`
- No error messages

### 3. Test Database Connectivity

```python
# In a Databricks notebook
from databricks.sdk import WorkspaceClient
import psycopg

w = WorkspaceClient()
cred = w.postgres.generate_database_credential(
    endpoint="projects/databricks-postgres-streamlit/endpoints/primary"
)

conn = psycopg.connect(
    host="ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com",
    dbname="databricks_postgres",
    user="your-email@company.com",
    password=cred.token,
    port=5432,
    sslmode="require",
)

cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM public.synced_well_production")
print(f"Row count: {cur.fetchone()[0]}")
cur.close()
conn.close()
```

### 4. Verify App Features

| Feature | How to Test | Expected Result |
|---------|-------------|----------------|
| Dashboard | Navigate to Dashboard page | KPI cards show well counts, oil/gas totals |
| Well List | Navigate to Well List page | Table shows 25 wells with filters |
| Add Well | Fill form and submit | New well appears in list |
| Edit Well | Select well and update status | Status changes in database |
| Delete Well | Select well and confirm | Well removed from database |
| Analytics | Navigate to Analytics page | Charts display production data |

---

## Rollback Procedure

### Option 1: Git Revert (Automated)

```bash
# Revert the merge commit on main
git checkout main
git pull origin main
git revert <merge-commit-sha>
git push origin main

# CD pipeline will auto-deploy the previous version
```

### Option 2: Manual Redeploy

```bash
# Deploy from the last known good commit
git checkout <last-good-commit-sha>
databricks apps deploy oil-gas-streamlit-app --source-path ./app
```

### Option 3: Databricks CLI Direct Deploy

```bash
# Deploy from any local state
export DATABRICKS_HOST=https://dbc-050f2fd4-a450.cloud.databricks.com
export DATABRICKS_TOKEN=your-token
databricks apps deploy oil-gas-streamlit-app --source-path ./app
```

---

## Common Deployment Issues

| Issue | Cause | Solution |
|-------|-------|---------|
| App fails to start | Missing dependencies | Check `requirements.txt` is complete |
| Connection refused | Endpoint scaled to zero | Wait ~100ms for wake-up, add retry logic |
| Authentication failed | Expired OAuth token | Use `generate_database_credential()` for fresh token |
| No data in app | Sync not complete | Check sync pipeline status, wait for initial sync |
| SSL error | Missing sslmode | Always use `sslmode="require"` |

See [troubleshooting.md](troubleshooting.md) for detailed solutions.

---

## Quick Reference

| Action | Command |
|--------|--------|
| Deploy app | `databricks apps deploy oil-gas-streamlit-app --source-path ./app` |
| Check status | `databricks apps get oil-gas-streamlit-app` |
| View logs | `databricks apps logs oil-gas-streamlit-app` |
| Local run | `streamlit run app.py` |
| Check sync | `w.postgres.get_synced_table(...)` |
| Generate token | `w.postgres.generate_database_credential(...)` |