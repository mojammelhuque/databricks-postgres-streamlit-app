# 📖 Project Description — Databricks Postgres Streamlit Apps

> **Comprehensive guide to the backend architecture, data flow, user interaction model, and secret management for the Oil & Gas Well Production Dashboard.**

---

## 📋 Table of Contents

1. [What This Project Is](#what-this-project-is)
2. [High-Level Architecture (One-Liner)](#high-level-architecture-one-liner)
3. [Backend Architecture — How Postgres Is Used](#backend-architecture--how-postgres-is-used)
4. [How Streamlit Is Used](#how-streamlit-is-used)
5. [How Users Interact](#how-users-interact)
6. [Secret Management](#secret-management)
7. [Data Flow Diagram](#data-flow-diagram)
8. [Component Interaction Details](#component-interaction-details)
9. [Deployment Options](#deployment-options)
10. [Key Design Decisions](#key-design-decisions)

---

## What This Project Is

This project is an **end-to-end data application** that demonstrates how to:

1. **Sync data** from a Databricks Unity Catalog Delta table to a **Lakebase Postgres** database using Reverse ETL.
2. **Build an interactive web app** with Streamlit that reads and writes to the Postgres database.
3. **Deploy the app** to multiple environments: Databricks Apps, Streamlit Community Cloud, or local development.

The data domain is **Oil & Gas well production** — 25 wells across 8 US basins with fields like oil rate, gas rate, water cut, well status, and geographic coordinates. The human-readable domain makes it easy for anyone to understand the data context.

---

## High-Level Architecture (One-Liner)

> Unity Catalog (Delta Lake) → Reverse ETL Sync → Lakebase Postgres (OLTP) → Streamlit Web App (CRUD + Dashboard) → User Browser

---

## Backend Architecture — How Postgres Is Used

### The Role of Lakebase Postgres

Lakebase Postgres is a **managed, serverless PostgreSQL database** that runs inside Databricks. It provides:

- **OLTP capabilities** — full INSERT, UPDATE, DELETE, and SELECT operations (unlike Delta Lake, which is optimized for analytics/OLAP).
- **Autoscaling** — scales from 0.5 to 32 compute units (CU) based on load, and scales to zero after 5 minutes of idle.
- **Branching** — copy-on-write branches for dev/test/prod isolation (like Git for databases).
- **OAuth token authentication** — short-lived tokens (1-hour expiry) generated via the Databricks SDK.

### How Data Gets Into Postgres

Data originates in **Unity Catalog** as a Delta Lake table:

```
workspace.oil_gas_ops.well_production (Delta Table, 25 rows)
```

A **Reverse ETL sync pipeline** (Lakeflow Spark Declarative Pipeline, ID: `a41bf65e-3ca8-4522-aebf-e196234fd973`) copies this data into Lakebase Postgres:

```
Source:  workspace.oil_gas_ops.well_production (Unity Catalog / Delta Lake)
Target:  databricks_postgres.oil_gas_ops.synced_well_production (Lakebase Postgres)
Mode:    Triggered (manual or scheduled sync)
Key:     well_id (primary key for upsert)
CDF:     Required on source table (delta.enableChangeDataFeed = true)
```

**Important**: The Reverse ETL sync preserves the schema name. Since the UC table is in schema `oil_gas_ops`, the Postgres table is created in schema `oil_gas_ops` — NOT in the default `public` schema. This was a key bug discovered during deployment.

### How the App Connects to Postgres

The Streamlit app uses **psycopg3** (PostgreSQL driver for Python) to connect directly to Lakebase Postgres via SSL:

```python
conn = psycopg.connect(
    host=lakebase_host,          # e.g., ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com
    dbname="databricks_postgres",
    user="mojammel.huque@gmail.com",
    password=oauth_token,         # SDK-generated, valid 1 hour
    port=5432,
    sslmode="require",            # SSL/TLS enforced
)
```

The connection is **cached for 45 minutes** using `@st.cache_resource(ttl=2700)` to avoid regenerating tokens on every request. The token expires after 1 hour, so the 45-minute cache ensures a fresh token is always available before expiry.

### SQL Operations Performed

The app performs full CRUD operations on the `oil_gas_ops.synced_well_production` table:

| Operation | SQL | Function in app.py |
|-----------|-----|---------------------|
| Read all wells | `SELECT * FROM oil_gas_ops.synced_well_production ORDER BY well_id` | `get_all_wells()` |
| Read single well | `SELECT * FROM ... WHERE well_id = %s` | `get_well_by_id()` |
| Insert well | `INSERT INTO ... (well_id, well_name, ...) VALUES (%s, %s, ...)` | `insert_well()` |
| Update status | `UPDATE ... SET well_status = %s WHERE well_id = %s` | `update_well_status()` |
| Update rates | `UPDATE ... SET oil_rate = %s, gas_rate = %s, ... WHERE well_id = %s` | `update_well_rates()` |
| Delete well | `DELETE FROM ... WHERE well_id = %s` | `delete_well()` |

All write operations include **transaction safety** — if a query fails, the connection is rolled back to prevent the "current transaction is aborted" error that locks subsequent operations.

---

## How Streamlit Is Used

### What Streamlit Does

Streamlit is a Python web framework that turns data scripts into interactive web applications with zero frontend code. In this project, Streamlit serves as the **entire presentation and interaction layer**:

### App Pages / Sections

The app provides these sections (all in a single `app.py` file):

| Section | What It Does | Backend Calls |
|---------|--------------|---------------|
| **Dashboard** | KPI cards (total wells, active wells, oil/gas production totals), status distribution chart | `SELECT` with aggregations |
| **Well List** | Sortable, filterable data table of all wells with basin/operator/status filters | `SELECT *` with ORDER BY |
| **Add Well** | Form to insert a new well record (well_id, name, operator, basin, rates, etc.) | `INSERT INTO` |
| **Edit Well** | Update well status (ACTIVE/SHUT_IN/MAINTENANCE) and production rates | `UPDATE` |
| **Delete Well** | Remove a well with confirmation dialog | `DELETE` |
| **Analytics** | Production by basin (bar chart), operator ranking (pie chart), production vs water cut scatter plot, well map with lat/lon | `SELECT` with GROUP BY |

### Why Streamlit (Not Flask/Dash/React)

- **Single-file app** — all UI, backend, and database logic in one `app.py` (simpler for demos and small teams).
- **Built-in caching** — `@st.cache_resource` for connection pooling, `@st.cache_data` for data caching.
- **No HTML/CSS/JS** — Streamlit generates the web UI from Python code.
- **Free hosting** — Streamlit Community Cloud hosts the app for free with auto-deploy from GitHub.
- **Plotly integration** — interactive charts (bar, pie, scatter, geographic maps) out of the box.

---

## How Users Interact

### User Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     USER BROWSER                             │
│                                                             │
│  User navigates to:                                         │
│  • Databricks App URL (private, identity-aware)             │
│  • Streamlit Cloud URL (public, e.g., app.streamlit.app)    │
│  • localhost:8501 (local dev)                               │
│                                                             │
│  User sees:                                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Sidebar: Navigation (Dashboard, Wells, Add, Edit)   │  │
│  │  Main Area:  Charts, Tables, Forms, Maps              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  User actions:                                              │
│  1. VIEW  → Click "Dashboard" → sees KPIs and charts       │
│  2. FILTER → Select basin/operator in sidebar → table     │
│              updates instantly                             │
│  3. ADD   → Click "Add Well" → fills form → clicks "Save" │
│             → app INSERTs to Postgres → table refreshes     │
│  4. EDIT  → Selects a well → changes status/rates →        │
│             clicks "Update" → app UPDATEs Postgres         │
│  5. DELETE → Selects a well → clicks "Delete" → confirms   │
│              → app DELETEs from Postgres                   │
│                                                             │
│  Each action triggers a SQL query against Lakebase Postgres │
│  Results are displayed in real-time (no page reload)       │
└─────────────────────────────────────────────────────────────┘
```

### Authentication Model

| Deployment | Auth Method | Who Can Access |
|------------|------------|----------------|
| Databricks App | Databricks identity (SSO/OAuth) | Workspace members with app access |
| Streamlit Cloud | Public URL (no auth) | Anyone with the URL |
| Local dev | None (localhost) | Only the developer |

**Note**: The Streamlit Cloud deployment is intentionally public for demo/portfolio purposes. For production with sensitive data, use Databricks Apps with identity-aware access.

---

## Secret Management

### Overview

Secrets are managed differently depending on the deployment environment. No secrets are ever committed to Git (verified by CI secret scan).

### Secret Flow by Environment

#### 1. Databricks App (Production-Grade)

```
Databricks Apps Platform
  ↓ Auto-injects environment variables at runtime:
  DATABRICKS_LAKEBASE_PG_HOST      → Postgres endpoint host
  DATABRICKS_LAKEBASE_PG_DATABASE  → Database name
  DATABRICKS_LAKEBASE_PG_USER      → Service principal email
  DATABRICKS_LAKEBASE_PG_PASSWORD  → OAuth token (auto-rotated)
  DATABRICKS_LAKEBASE_PG_PORT      → 5432
  ↓
  app.py reads os.environ → psycopg connects to Postgres
```

- **Zero-config**: No manual secret management. Databricks handles everything.
- **Auto-rotation**: OAuth tokens rotate every 60 minutes automatically.
- **Isolation**: Secrets are injected at runtime, never stored in the app container.

#### 2. Streamlit Community Cloud (Free Tier)

```
Streamlit Cloud Dashboard → Settings → Secrets
  ↓ User manually enters TOML-format secrets:
  DATABRICKS_HOST     = "https://dbc-xxxxx.cloud.databricks.com"
  DATABRICKS_TOKEN    = "dapiXXXXXXXXXX"  (PAT, 90-day expiry)
  LAKEBASE_PG_HOST    = "ep-xxxxx.database.us-east-2.cloud.databricks.com"
  LAKEBASE_PG_USER    = "user@email.com"
  LAKEBASE_PG_DB      = "databricks_postgres"
  LAKEBASE_PG_PORT    = "5432"
  LAKEBASE_PROJECT    = "databricks-postgres-streamlit"
  LAKEBASE_BRANCH     = "production"
  ↓
  app.py reads st.secrets.get("KEY") with fallback to os.environ
  ↓
  Databricks SDK uses PAT to generate fresh OAuth token:
    w = WorkspaceClient(host=DATABRICKS_HOST, token=DATABRICKS_TOKEN)
    cred = w.postgres.generate_database_credential(
        endpoint="projects/{project}/branches/{branch}/endpoints/primary"
    )
    # cred.token is a short-lived OAuth token (1-hour expiry)
  ↓
  psycopg connects to Postgres using SDK-generated token as password
  ↓
  Connection cached for 45 minutes via @st.cache_resource(ttl=2700)
```

- **Two-layer auth**: PAT (long-lived, 90 days) → OAuth token (short-lived, 1 hour).
- **Auto-refresh**: SDK generates a new OAuth token every 45 minutes (cached). PAT never sent to Postgres.
- **Manual PAT renewal**: Every 90 days, the user must generate a new PAT in Databricks settings and update Streamlit secrets.
- **Secrets encrypted at rest**: Streamlit Cloud encrypts secrets; they are not visible to app viewers.

#### 3. Local Development

```
Developer's .env file (git-ignored via .gitignore):
  LAKEBASE_PG_HOST=ep-xxxxx.database.us-east-2.cloud.databricks.com
  LAKEBASE_PG_USER=user@email.com
  LAKEBASE_PG_PASSWORD=<oauth-token-or-pat>
  LAKEBASE_PG_DB=databricks_postgres
  LAKEBASE_PG_PORT=5432
  ↓
  app.py reads os.environ → psycopg connects directly
```

- **Manual**: Developer manages their own tokens.
- **No SDK**: Local dev can use a direct OAuth token or PAT as the Postgres password.

### Secret Hierarchy Summary

```
Security Level (highest to lowest):
  1. Databricks App     → Fully managed, auto-rotated, no manual secrets
  2. Streamlit Cloud    → PAT (manual, 90-day) → SDK → OAuth token (auto, 1-hour)
  3. Local Dev          → Manual token in .env file (developer's responsibility)
```

---

## Data Flow Diagram

### Complete System Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              COMPLETE DATA FLOW                                     │
│                                                                                     │
│  ┌─────────────────────┐                                                           │
│  │   Databricks        │                                                           │
│  │   Unity Catalog     │   TIER 1: DATA SOURCE                                    │
│  │                     │                                                           │
│  │  workspace.         │   • Delta Lake table with ACID transactions               │
│  │  oil_gas_ops.        │   • Change Data Feed (CDF) enabled                       │
│  │  well_production    │   • 25 wells, 8 basins, 17 operators                     │
│  │  (Delta Table)       │   • Fields: well_id, well_name, oil_rate, gas_rate,      │
│  │                     │     water_cut, well_status, lat/lon, etc.                  │
│  └──────────┬──────────┘                                                           │
│             │                                                                        │
│             │  Reverse ETL Sync (Triggered)                                         │
│             │  Pipeline: a41bf65e-3ca8-4522-aebf-e196234fd973                     │
│             │  Mode: TRIGGERED (manual or scheduled)                                │
│             │  PK: well_id (upsert)                                                 │
│             │  CDF: Required (enabled on source)                                    │
│             │                                                                        │
│  ┌──────────▼──────────┐                                                           │
│  │  Databricks         │   TIER 2: POSTGRES DATABASE                               │
│  │  Lakebase Postgres   │                                                           │
│  │                     │   • Managed serverless PostgreSQL                          │
│  │  Project:           │   • Autoscaling: 0.5-32 CU, scale-to-zero in 5 min       │
│  │  databricks-        │   • Branch: production (copy-on-write)                   │
│  │  postgres-streamlit │   • Endpoint: primary (read-write, scale-to-zero)        │
│  │                     │   • Host: ep-patient-term-d801116u...                      │
│  │  Database:          │   • Database: databricks_postgres                         │
│  │  databricks_postgres│   • Schema: oil_gas_ops (matches UC schema name)         │
│  │                     │   • Table: synced_well_production (25 rows)               │
│  │  Table:             │   • Auth: OAuth token (1-hour expiry, SDK-generated)     │
│  │  synced_well_       │   • SSL/TLS required on all connections                  │
│  │  production         │                                                           │
│  └──────────┬──────────┘                                                           │
│             │                                                                        │
│             │  psycopg3 (PostgreSQL driver for Python)                             │
│             │  Connection cached 45 min (@st.cache_resource)                       │
│             │  SSL: sslmode="require"                                               │
│             │                                                                        │
│  ┌──────────▼──────────────────────────────────────────────────┐                  │
│  │                    CONNECTION LAYER                           │                  │
│  │                                                              │                  │
│  │  ┌─────────────────────────────────────────────────────┐    │                  │
│  │  │  PATH 1: Databricks App                              │    │                  │
│  │  │  • Auto-injected env vars (DATABRICKS_LAKEBASE_PG_*) │    │                  │
│  │  │  • OAuth token auto-rotated every 60 min             │    │                  │
│  │  │  • Zero-config, no manual secrets needed             │    │                  │
│  │  └─────────────────────────────────────────────────────┘    │                  │
│  │                                                              │                  │
│  │  ┌─────────────────────────────────────────────────────┐    │                  │
│  │  │  PATH 2: Streamlit Community Cloud                   │    │                  │
│  │  │  • st.secrets → DATABRICKS_HOST + DATABRICKS_TOKEN    │    │                  │
│  │  │  • Databricks SDK: WorkspaceClient(host, token)      │    │                  │
│  │  │  • SDK calls: w.postgres.generate_database_credential│    │                  │
│  │  │    endpoint="projects/{project}/branches/{branch}/   │    │                  │
│  │  │             endpoints/primary"                      │    │                  │
│  │  │  • Returns: cred.token (OAuth, 1-hour expiry)        │    │                  │
│  │  │  • Cached: 45 min via @st.cache_resource(ttl=2700)  │    │                  │
│  │  │  • PAT (dapi...) is NOT sent to Postgres — only     │    │                  │
│  │  │    the SDK-generated OAuth token is used as password │    │                  │
│  │  └─────────────────────────────────────────────────────┘    │                  │
│  │                                                              │                  │
│  │  ┌─────────────────────────────────────────────────────┐    │                  │
│  │  │  PATH 3: Local Development                            │    │                  │
│  │  │  • .env file → LAKEBASE_PG_* environment variables   │    │                  │
│  │  │  • Direct psycopg.connect() with manual token/PAT    │    │                  │
│  │  │  • Or: LAKEBASE_PG_URL full connection string        │    │                  │
│  │  └─────────────────────────────────────────────────────┘    │                  │
│  └──────────┬──────────────────────────────────────────────────┘                  │
│             │                                                                        │
│  ┌──────────▼──────────────────────────────────────────────────┐                  │
│  │                    STREAMLIT APP (app.py)                    │  TIER 3: APP    │
│  │                                                              │                  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │                  │
│  │  │  Dashboard  │  │  Well List   │  │  Analytics      │    │                  │
│  │  │             │  │              │  │                 │    │                  │
│  │  │ • KPI cards│  │ • Data table │  │ • Bar charts    │    │                  │
│  │  │ • Status   │  │ • Filters   │  │ • Pie charts    │    │                  │
│  │  │   donut    │  │ • Sort by   │  │ • Scatter plots │    │                  │
│  │  │ • Summary  │  │   basin/    │  │ • Well map      │    │                  │
│  │  │   stats    │  │   operator  │  │   (lat/lon)     │    │                  │
│  │  └─────────────┘  └──────────────┘  └─────────────────┘    │                  │
│  │                                                              │                  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │                  │
│  │  │  Add Well   │  │  Edit Well   │  │  Delete Well    │    │                  │
│  │  │             │  │              │  │                 │    │                  │
│  │  │ • Form with │  │ • Select well│  │ • Select well   │    │                  │
│  │  │   validation│  │ • Change     │  │ • Confirm       │    │                  │
│  │  │ • INSERT to │  │   status/    │  │ • DELETE from   │    │                  │
│  │  │   Postgres  │  │   rates      │  │   Postgres      │    │                  │
│  │  │ • Error     │  │ • UPDATE     │  │ • Confirmation  │    │                  │
│  │  │   handling  │  │   Postgres   │  │   dialog        │    │                  │
│  │  └─────────────┘  └──────────────┘  └─────────────────┘    │                  │
│  │                                                              │                  │
│  │  Transaction Safety: try-except with conn.rollback() on     │                  │
│  │  error → prevents "current transaction is aborted" lockup   │                  │
│  └──────────┬──────────────────────────────────────────────────┘                  │
│             │                                                                        │
│  ┌──────────▼──────────────────────────────────────────────────┐                  │
│  │                    DEPLOYMENT OPTIONS                        │  TIER 4: HOST  │
│  │                                                              │                  │
│  │  ┌──────────────────┐  ┌──────────────────┐                 │                  │
│  │  │ Databricks App   │  │ Streamlit Cloud  │  ┌────────────┐ │                  │
│  │  │ (oil-gas-        │  │ (share.          │  │ Local /    │ │                  │
│  │  │  streamlit-app)  │  │  streamlit.io)   │  │ RStudio    │ │                  │
│  │  │                  │  │                  │  │            │ │                  │
│  │  │ • Auto-deploy    │  │ • Free hosting  │  │ • Dev only │ │                  │
│  │  │   via GitHub     │  │ • Auto-deploy   │  │ • Env vars │ │                  │
│  │  │   Actions CI/CD  │  │   from GitHub   │  │ • .env     │ │                  │
│  │  │ • Auto-rotated   │  │   push to main  │  │   file     │ │                  │
│  │  │   OAuth tokens   │  │ • SDK token     │  │ • Manual   │ │                  │
│  │  │ • Identity-aware │  │   refresh (45m) │  │   tokens  │ │                  │
│  │  │ • Private access │  │ • Public URL    │  │ • localhost│ │                  │
│  │  │ • Managed SSL    │  │ • Free SSL      │  │            │ │                  │
│  │  └──────────────────┘  └──────────────────┘  └────────────┘ │                  │
│  └──────────────────────────────────────────────────────────────┘                  │
│             │                                                                        │
│  ┌──────────▼──────────┐                                                           │
│  │   USER BROWSER      │   TIER 5: USER                                            │
│  │                     │                                                           │
│  │  • Interactive UI   │                                                           │
│  │  • Charts & tables  │                                                           │
│  │  • CRUD forms       │                                                           │
│  │  • Real-time updates│                                                           │
│  └─────────────────────┘                                                           │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Simplified Data Flow (Quick Reference)

```
Unity Catalog Delta Table
        │
        │ Reverse ETL (Triggered sync)
        ▼
Lakebase Postgres (oil_gas_ops.synced_well_production)
        │
        │ psycopg3 + SSL/TLS + OAuth token
        ▼
Streamlit App (app.py)
        │
        │ HTTP (browser to app server)
        ▼
User Browser (dashboard, CRUD, analytics)
```

### Token Generation Flow (Streamlit Cloud)

```
Streamlit Secrets (TOML)
  ├── DATABRICKS_HOST  ─────────────────┐
  ├── DATABRICKS_TOKEN (PAT, 90-day)   ─┤
  ├── LAKEBASE_PG_HOST                ─┤
  ├── LAKEBASE_PG_USER                ─┤
  └── LAKEBASE_PROJECT / BRANCH       ─┤
                                      │
                                      ▼
                            WorkspaceClient(host, token)
                                      │
                                      │  w.postgres.generate_database_credential(
                                      │    endpoint="projects/{project}/branches/{branch}/endpoints/primary"
                                      │  )
                                      │
                                      ▼
                              OAuth Token (1-hour expiry)
                                      │
                                      │  Used as password in:
                                      │  psycopg.connect(host=..., password=cred.token, ...)
                                      │
                                      ▼
                              Lakebase Postgres Connection
                                      │
                                      │  @st.cache_resource(ttl=2700)
                                      │  (cached for 45 minutes)
                                      │
                                      ▼
                              SQL Queries (SELECT, INSERT, UPDATE, DELETE)
```

---

## Component Interaction Details

### 1. Unity Catalog to Lakebase Postgres (Reverse ETL)

| Aspect | Detail |
|--------|--------|
| Source table | `workspace.oil_gas_ops.well_production` |
| Target table | `databricks_postgres.oil_gas_ops.synced_well_production` |
| Sync pipeline | Lakeflow Spark Declarative Pipeline (ID: `a41bf65e...`) |
| Sync mode | Triggered (manual or scheduled) |
| Primary key | `well_id` (used for upsert) |
| CDF requirement | Change Data Feed must be enabled on source |
| Schema preservation | UC schema `oil_gas_ops` maps to Postgres schema `oil_gas_ops` |
| Sync rate | ~150 rows/sec per CU |

### 2. Streamlit App to Lakebase Postgres (psycopg3)

| Aspect | Detail |
|--------|--------|
| Driver | psycopg3 (PostgreSQL driver for Python) |
| Connection string | `host=..., dbname=databricks_postgres, user=..., password=oauth_token, port=5432, sslmode=require` |
| Caching | `@st.cache_resource(ttl=2700)` — 45-minute cache |
| Schema | `oil_gas_ops` (NOT `public` — this was a key bug fix) |
| Table | `synced_well_production` |
| Transaction safety | `try-except` with `conn.rollback()` on error |
| Error handling | Real database errors surfaced to UI (e.g., duplicate key, constraint violations) |

### 3. Databricks SDK to Token Generation (Streamlit Cloud only)

| Aspect | Detail |
|--------|--------|
| SDK class | `WorkspaceClient(host=DATABRICKS_HOST, token=DATABRICKS_TOKEN)` |
| Method | `w.postgres.generate_database_credential(endpoint=...)` |
| Endpoint format | `projects/{project}/branches/{branch}/endpoints/primary` |
| Token type | OAuth (1-hour expiry) |
| Token usage | Used as `password` parameter in `psycopg.connect()` |
| Refresh | Automatic via `@st.cache_resource(ttl=2700)` (45 min cache) |
| PAT (input) | Never sent to Postgres — only used to authenticate SDK calls |

---

## Deployment Options

### Comparison Matrix

| Feature | Databricks App | Streamlit Cloud | Local Dev |
|---------|---------------|-----------------|-----------|
| Cost | Included in Databricks | Free | Free |
| Auth | Databricks SSO | Public URL | None |
| Token rotation | Auto (60 min) | SDK (45 min cache) | Manual |
| Auto-deploy | GitHub Actions CI/CD | GitHub push to main | Manual |
| SSL | Managed | Managed | Manual |
| Scale | Managed | Shared resources | Developer machine |
| Best for | Production | Demo/portfolio | Development |

---

## Key Design Decisions

### 1. Why psycopg3 (not PostgREST Data API)?

The app uses **direct SQL via psycopg3** as the primary connection method because:
- Full SQL capabilities (complex queries, aggregations, JOINs)
- Transaction control (BEGIN, COMMIT, ROLLBACK)
- Better debugging (raw SQL visible in error messages)
- No HTTP overhead for database operations

The PostgREST Data API remains available as an alternative for HTTP-based CRUD, but is not used in the current implementation.

### 2. Why `oil_gas_ops` schema (not `public`)?

The Reverse ETL sync pipeline preserves the Unity Catalog schema name. Since the source table is `workspace.oil_gas_ops.well_production`, the Postgres table is created in schema `oil_gas_ops` — NOT in `public`. The app hardcodes `SCHEMA_NAME = "oil_gas_ops"` to match.

### 3. Why 45-minute token cache?

OAuth tokens expire after 1 hour. Caching for 45 minutes ensures:
- A fresh token is always available before the 1-hour expiry.
- Reduces SDK API calls (generate_database_credential) by 97% (from ~60/hour to ~1.3/hour).
- If the cached connection drops, the next request regenerates a fresh token.

### 4. Why transaction rollback?

PostgreSQL aborts the entire transaction when any statement fails. Without `conn.rollback()`, the connection enters an "aborted" state where all subsequent commands fail with:
```
current transaction is aborted, commands ignored until end of transaction block
```
The `execute_query()` function wraps all operations in `try-except` with automatic rollback to prevent this.

---

## Resource Inventory

| Resource | Identifier | Type |
|----------|-----------|------|
| UC Catalog | `workspace` | Unity Catalog |
| UC Schema | `workspace.oil_gas_ops` | Schema |
| UC Table (source) | `workspace.oil_gas_ops.well_production` | Delta Table |
| UC Synced Table | `workspace.oil_gas_ops.synced_well_production` | Synced Table |
| Lakebase Project | `databricks-postgres-streamlit` | Postgres Project |
| Lakebase Branch | `production` | Branch (copy-on-write) |
| Lakebase Endpoint | `primary` | Read-Write Endpoint (scale-to-zero) |
| Lakebase Database | `databricks_postgres` | Database |
| Lakebase Table | `oil_gas_ops.synced_well_production` | Postgres Table (25 rows) |
| Sync Pipeline | `a41bf65e-3ca8-4522-aebf-e196234fd973` | SDP Pipeline |
| Postgres Host | `ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com` | Endpoint URL |
| GitHub Repo | `mojammelhuque/databricks-postgres-streamlit-app` | Git Repository |
| Databricks App | `oil-gas-streamlit-app` | Databricks App |
| Streamlit Cloud | `https://<app-name>.streamlit.app` | Streamlit Cloud App |

---

## Author

Mojammel Huque — [GitHub](https://github.com/mojammelhuque)

---

## Related Documentation

| Document | Description |
|----------|-------------|
| [README.md](../README.md) | Project overview and quick start guide |
| [architecture.md](architecture.md) | Detailed system architecture and data flow |
| [streamlit_cloud_deployment.md](streamlit_cloud_deployment.md) | Streamlit Cloud setup guide |
| [deployment_guide.md](deployment_guide.md) | Databricks App and local deployment |
| [troubleshooting.md](troubleshooting.md) | Common issues and solutions |
| [security.md](security.md) | Security architecture and best practices |
| [data_dictionary.md](data_dictionary.md) | Field-by-field data dictionary |
| [DEPLOYMENT_SUMMARY.md](../DEPLOYMENT_SUMMARY.md) | Deployment timeline and lessons learned |
