# ☁️ Streamlit Community Cloud Deployment

> Deploy your Oil & Gas Well Production Dashboard to Streamlit Community Cloud (FREE).

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Setup](#step-by-step-setup)
5. [Streamlit Secrets Configuration](#streamlit-secrets-configuration)
6. [Generating a Databricks PAT](#generating-a-databricks-pat)
7. [Finding Your Lakebase Endpoint Host](#finding-your-lakebase-endpoint-host)
8. [Troubleshooting](#troubleshooting)
9. [Limitations](#limitations)

---

## Overview

[Streamlit Community Cloud](https://share.streamlit.io/) is a free hosting platform for Streamlit apps. Your app will be publicly accessible with a URL like `https://your-app-name.streamlit.app`.

### Key Features

* **Free** - No cost for public apps
* **Auto-deploy** from GitHub on every push
* **Secrets management** via Streamlit dashboard
* **Auto-sleep** when idle (wakes on request)
* **Custom URL** (`your-app-name.streamlit.app`)

---

## How It Works

The app uses a **3-path connection strategy** to handle different environments:

```
Path 1: Databricks Apps    → Auto-injected credentials (app.yaml)
Path 2: Streamlit Cloud     → Databricks SDK token refresh (st.secrets)
Path 3: Local Development   → Environment variables (.env)
```

On Streamlit Cloud, **Path 2** activates:

1. App reads `DATABRICKS_HOST` and `DATABRICKS_TOKEN` from Streamlit secrets
2. Uses Databricks SDK to generate a fresh Lakebase Postgres OAuth token
3. Connects to Postgres with the fresh token
4. Token auto-refreshes every 45 minutes (cached via `@st.cache_resource`)

This means your app stays connected indefinitely without manual token refresh!

---

## Prerequisites

* A GitHub repository (already set up: `databricks-postgres-streamlit-app`)
* A Databricks account with Lakebase Postgres access
* A Databricks Personal Access Token (PAT)
* Your Lakebase Postgres endpoint host

---

## Step-by-Step Setup

### Step 1: Go to Streamlit Community Cloud

Visit [https://share.streamlit.io/](https://share.streamlit.io/) and sign in with your GitHub account.

### Step 2: Create a New App

1. Click **"New app"** (or "Create app")
2. Select your repository: `mojammelhuque/databricks-postgres-streamlit-app`
3. Select branch: `main` (or `dev` for testing)
4. Set main file path: `app/app.py`
5. Click **"Deploy!"**

### Step 3: Wait for Initial Build

Streamlit will:
1. Clone your repo
2. Install dependencies from `app/requirements.txt`
3. Launch `app/app.py`

This takes 2-5 minutes. The app will show a connection error initially — that's expected!

### Step 4: Configure Secrets

1. Go to your app dashboard on Streamlit Cloud
2. Click the **three dots** (menu) in the bottom right of your app
3. Click **"Settings"**
4. Click **"Secrets"** tab
5. Paste the secrets configuration (see next section)
6. Click **"Save"**
7. Your app will automatically restart with the new secrets

---

## Streamlit Secrets Configuration

Paste this into the Streamlit Secrets text box, replacing the placeholder values:

```toml
# Databricks workspace connection (for SDK token generation)
DATABRICKS_HOST = "https://dbc-050f2fd4-a450.cloud.databricks.com"
DATABRICKS_TOKEN = "dapi1234567890abcdef..."

# Lakebase Postgres connection details
LAKEBASE_PG_HOST = "ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com"
LAKEBASE_PG_USER = "mojammel.huque@gmail.com"
LAKEBASE_PG_DB = "databricks_postgres"
LAKEBASE_PG_PORT = "5432"

# Lakebase project name (optional, defaults to databricks-postgres-streamlit)
LAKEBASE_PROJECT = "databricks-postgres-streamlit"
```

### Secrets Reference

| Secret | Required | Description |
|--------|----------|-------------|
| `DATABRICKS_HOST` | Yes | Your Databricks workspace URL |
| `DATABRICKS_TOKEN` | Yes | Databricks PAT (see below) |
| `LAKEBASE_PG_HOST` | Yes | Lakebase Postgres endpoint hostname |
| `LAKEBASE_PG_USER` | Yes | Your Databricks email |
| `LAKEBASE_PG_DB` | No | Database name (default: `databricks_postgres`) |
| `LAKEBASE_PG_PORT` | No | Port (default: `5432`) |
| `LAKEBASE_PROJECT` | No | Project name (default: `databricks-postgres-streamlit`) |

---

## Generating a Databricks PAT

Your Databricks Personal Access Token (PAT) allows the app to generate fresh Lakebase Postgres credentials.

### Option A: Databricks UI

1. Go to your Databricks workspace: `https://dbc-050f2fd4-a450.cloud.databricks.com`
2. Click your username (top right) > **Settings**
3. Go to **Developer** > **Access tokens**
4. Click **Generate new token**
5. Set comment: `Streamlit Cloud App`
6. Set lifetime: **90 days** (maximum)
7. Copy the token (starts with `dapi...`)
8. Paste it as `DATABRICKS_TOKEN` in Streamlit secrets

### Option B: Databricks CLI

```bash
databricks tokens create --comment "Streamlit Cloud App" --lifetime-seconds 7776000
```

### Important Notes

* PATs expire (set 90 days for maximum lifetime)
* You must regenerate and update the secret before it expires
* The PAT only needs access to generate Lakebase credentials — no other permissions required
* The PAT is stored encrypted in Streamlit Cloud secrets

---

## Finding Your Lakebase Endpoint Host

Your Lakebase Postgres endpoint host is already known:

```
ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com
```

If you need to find it again:

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
endpoint = w.postgres.get_endpoint(
    name="projects/databricks-postgres-streamlit/endpoints/primary"
)
print(f"Host: {endpoint.host}")
```

---

## Troubleshooting

### App shows "Databricks SDK connection failed"

* Check that `DATABRICKS_HOST` includes `https://`
* Verify `DATABRICKS_TOKEN` is valid and not expired
* Ensure the PAT has Lakebase Postgres access
* Check the error message details (shown in the app UI)

### App shows "databricks-sdk is required"

* Verify `requirements.txt` includes `databricks-sdk>=0.118.0`
* Check that the file is in the `app/` directory
* Redeploy the app

### App shows "Set LAKEBASE_PG_HOST in Streamlit secrets"

* Add `LAKEBASE_PG_HOST` to your Streamlit secrets
* Value should be: `ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com`

### App goes to sleep / takes time to load

* Streamlit Cloud apps sleep after inactivity (normal for free tier)
* First load takes ~10-30 seconds to wake up
* The Lakebase endpoint also scales to zero — add a few seconds for wake-up

### Data not showing / empty dashboard

* Check that the Reverse ETL sync is complete
* Verify the synced table has data in Postgres
* Try running a manual sync update from Databricks

---

## Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| App sleeps after inactivity | 10-30s cold start | Normal for free tier |
| PAT expires (90 days) | App stops working | Set calendar reminder to refresh |
| Public URL | Anyone can access the app | App is read-only for most operations |
| Resource limits | 1GB RAM, limited CPU | Fine for this dataset (25 rows) |
| No custom domain | URL is `*.streamlit.app` | Acceptable for demo/portfolio |

### Security Considerations

* The app URL is **public** — anyone can access it
* All operations (read/write) are available to anyone
* The PAT is stored in Streamlit's encrypted secrets (not visible to users)
* Consider adding authentication (Streamlit doesn't have built-in auth on free tier)
* For production use, prefer Databricks Apps (private, auto-configured)

---

## Quick Reference

| Item | Value |
|------|-------|
| Streamlit Cloud URL | https://share.streamlit.io/ |
| GitHub Repo | mojammelhuque/databricks-postgres-streamlit-app |
| Main File | app/app.py |
| Requirements | app/requirements.txt |
| Databricks Host | https://dbc-050f2fd4-a450.cloud.databricks.com |
| Lakebase Host | ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com |
| Lakebase Project | databricks-postgres-streamlit |
| Database | databricks_postgres |
| Table | public.synced_well_production |