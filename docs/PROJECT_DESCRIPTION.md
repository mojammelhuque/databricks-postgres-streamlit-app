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
11. [Concurrency Control — Preventing Lost Updates](#concurrency-control--preventing-lost-updates)

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

## Concurrency Control — Preventing Lost Updates

### The Problem: Lost Updates

When multiple users read and write to the **same row** simultaneously, PostgreSQL's MVCC (Multi-Version Concurrency Control) can silently drop one user's update:

```
Time 0: User A reads  → well_id=1, updated_at=14:30, oil_rate=850
Time 1: User B reads  → well_id=1, updated_at=14:30, oil_rate=850
Time 2: User A saves  → oil_rate=900  ✅ committed (updated_at → 14:35)
Time 3: User B saves  → oil_rate=800  ✅ committed (updated_at → 14:40)
                       ↑ User A's update is LOST — User B never saw it
```

PostgreSQL's default isolation level (READ COMMITTED) does not prevent this. Both transactions read the same old value, and the last writer wins silently.

### How PostgreSQL Handles Concurrency (MVCC)

PostgreSQL uses **Multi-Version Concurrency Control** as its foundation:

```
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL MVCC Model                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Readers NEVER block writers                                │
│  Writers NEVER block readers                                │
│  Writers only block OTHER writers on the SAME row           │
│                                                             │
│  Each transaction sees a consistent snapshot:                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  Transaction A │    │  Transaction B │    │  Transaction C │   │
│  │  (reads row)  │    │  (reads row)  │    │  (writes row) │   │
│  │  sees version │    │  sees version │    │  creates new  │   │
│  │  @ 14:30     │    │  @ 14:30     │    │  version @    │   │
│  │              │    │              │    │  14:35        │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                             │
│  Problem: MVCC prevents dirty reads but NOT lost updates.   │
│  Solution: Application-level locking (optimistic or          │
│  pessimistic) is needed to detect/handle conflicts.          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Two Approaches to Prevent Lost Updates

This project implements **optimistic locking** (Approach 1), but both approaches are documented below for future reference and scaling decisions.

---

### Approach 1: Optimistic Locking (Implemented)

**How it works:** Uses the existing `updated_at` timestamp as a version check. When updating a row, the `WHERE` clause includes the original `updated_at` value the user saw when they loaded the page. If another user modified the row since then, `updated_at` will have changed, and the `UPDATE` will affect 0 rows.

**No schema changes needed** — the `updated_at` column already exists on `synced_well_production`.

#### SQL: Update with Optimistic Locking

```sql
-- Step 1: User reads the well (app captures updated_at)
SELECT well_id, well_status, updated_at
FROM oil_gas_ops.synced_well_production
WHERE well_id = 1;
-- Result: well_id=1, well_status='ACTIVE', updated_at='2026-09-20 14:30:00'

-- Step 2: User submits update (app includes updated_at in WHERE)
UPDATE oil_gas_ops.synced_well_production
SET well_status = 'SHUT_IN', updated_at = NOW()
WHERE well_id = 1 AND updated_at = '2026-09-20 14:30:00'
RETURNING well_id, updated_at;
-- If 1 row returned: success (updated_at → 2026-09-20 14:35:00)
-- If 0 rows returned: stale data — another user modified this row first
```

#### Code: Implementation in app.py

```python
def update_well_status(conn, well_id, new_status, previous_updated_at):
    """Update with optimistic locking — pass the updated_at the user originally read."""
    columns, rows = execute_query(conn, """
        UPDATE oil_gas_ops.synced_well_production
        SET well_status = %s, updated_at = %s
        WHERE well_id = %s AND updated_at = %s
        RETURNING well_id, updated_at
    """, (new_status, datetime.now(), well_id, previous_updated_at))

    if not rows:
        raise Exception(
            "⚠️ Stale data: this well was modified by another user since you last viewed it. "
            "Please refresh the page and try again."
        )
```

#### Streamlit UI: Capturing updated_at

```python
# When user selects a well to edit, capture its updated_at
well = get_well_by_id(conn, selected_well_id)
well_updated_at = well['updated_at']  # Store for optimistic locking check

# When user submits the form, pass the captured updated_at
update_well_status(conn, selected_well_id, new_status, well_updated_at)
# If stale → user sees: "⚠️ Stale data: this well was modified by another user..."
```

#### Flow Diagram

```
User A                          User B                    PostgreSQL
  │                               │                         │
  │── SELECT well_id=1 ──────────┼─────────────────────────▶│
  │◀─ updated_at=14:30 ──────────┼─────────────────────────│
  │                               │                         │
  │                               │── SELECT well_id=1 ────▶│
  │                               │◀─ updated_at=14:30 ─────│
  │                               │                         │
  │── UPDATE ... WHERE            │                         │
  │   updated_at=14:30 ──────────┼────────────────────────▶│
  │◀─ 1 row affected ✅ ──────────┼─────────────────────────│
  │   (updated_at → 14:35)        │                         │
  │                               │                         │
  │                               │── UPDATE ... WHERE      │
  │                               │   updated_at=14:30 ────▶│
  │                               │◀─ 0 rows affected ❌ ───│
  │                               │   (updated_at is now    │
  │                               │    14:35, not 14:30)    │
  │                               │                         │
  │                               │── Show "stale data"     │
  │                               │   error to user B       │
  │                               │── User B refreshes       │
  │                               │   and retries ✅         │
```

---

### Approach 2: Pessimistic Locking (Alternative — Not Implemented)

**How it works:** Locks the row at the database level using `SELECT ... FOR UPDATE`. Other users trying to modify the same row are blocked until the lock is released (transaction commits or rolls back). A `lock_timeout` prevents indefinite waits.

#### SQL: Pessimistic Locking

```sql
-- Set a timeout so users don't wait forever
SET lock_timeout = '5s';

-- Lock the row (other writers BLOCK here until this transaction completes)
SELECT well_id FROM oil_gas_ops.synced_well_production
WHERE well_id = 1
FOR UPDATE;

-- Now safe to update — no one else can modify this row
UPDATE oil_gas_ops.synced_well_production
SET well_status = 'SHUT_IN', updated_at = NOW()
WHERE well_id = 1;

COMMIT;  -- Releases the lock; other waiting users can proceed
```

#### Code: Pessimistic Locking (Alternative Implementation)

```python
def update_well_status_pessimistic(conn, well_id, new_status):
    """Update with row-level lock — other users wait until this transaction completes."""
    cur = conn.cursor()
    try:
        cur.execute("SET lock_timeout = '5s'")
        # Lock the row (other writers block here)
        cur.execute("""
            SELECT well_id FROM oil_gas_ops.synced_well_production
            WHERE well_id = %s FOR UPDATE
        """, (well_id,))
        if not cur.fetchone():
            cur.close()
            raise Exception("Well not found")

        cur.execute("""
            UPDATE oil_gas_ops.synced_well_production
            SET well_status = %s, updated_at = %s
            WHERE well_id = %s
        """, (new_status, datetime.now(), well_id))
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        cur.close()
        raise Exception(f"Database error: {str(e)}")
```

#### Flow Diagram

```
User A                          User B                    PostgreSQL
  │                               │                         │
  │── SELECT ... FOR UPDATE ──────┼────────────────────────▶│
  │◀─ Row locked ✅ ──────────────┼─────────────────────────│
  │                               │                         │
  │── UPDATE well_id=1 ───────────┼────────────────────────▶│
  │◀─ 1 row affected ✅ ──────────┼─────────────────────────│
  │                               │                         │
  │── COMMIT ─────────────────────┼────────────────────────▶│
  │   (lock released)             │                         │
  │                               │                         │
  │                               │── SELECT ... FOR UPDATE ▶│
  │                               │   (was blocked, now      │
  │                               │    proceeds)             │
  │                               │◀─ Row locked ✅ ─────────│
  │                               │                         │
  │                               │── UPDATE well_id=1 ─────▶│
  │                               │◀─ 1 row affected ✅ ─────│
  │                               │── COMMIT ───────────────▶│
```

---

### Which One to Choose?

| Factor | Optimistic Locking (Approach 1) | Pessimistic Locking (Approach 2) |
|--------|-------------------------------|----------------------------------|
| **How it works** | Check `updated_at` in WHERE clause; fail if stale | Lock row with `SELECT FOR UPDATE`; block others |
| **When conflicts are rare** | ✅ Best — no overhead, fast | ⚠️ Overkill — unnecessary locks |
| **When conflicts are frequent** | ⚠️ Many retries, user frustration | ✅ Best — orderly queuing |
| **User experience on conflict** | Clear error: "stale data, please refresh" | Wait (blocked) for up to 5 seconds |
| **Performance** | No locks held; readers/writers never blocked | Row locks held during transaction |
| **Deadlock risk** | None | Possible (mitigated with `lock_timeout`) |
| **Schema changes needed** | None (uses existing `updated_at`) | None |
| **Code complexity** | Low — add `updated_at` to WHERE + check row count | Medium — `SELECT FOR UPDATE`, `lock_timeout`, cursor management |
| **Best for** | Read-heavy, occasional writes, many users | Write-heavy on same rows, fewer users |
| **Network efficiency** | Single round-trip (UPDATE + RETURNING) | Two round-trips (SELECT FOR UPDATE + UPDATE) |
| **Scalability** | Scales well — no held locks | Limited by lock contention |
| **Streamlit compatibility** | ✅ Perfect — forms submit once, no long-held connections | ⚠️ Risky — Streamlit connections may time out during lock waits |

### Recommendation: Why Optimistic Locking (Approach 1) Was Chosen

**Optimistic locking is the right choice for this project for the following reasons:**

1. **No schema changes required.** The `updated_at` column already exists on the `synced_well_production` table. Optimistic locking reuses it as a version check with zero database changes.

2. **Low conflict rate in Oil & Gas domain.** Well production data is read frequently (dashboards, analytics, lists) but edited occasionally (status changes, rate updates). Two users editing the exact same well at the exact same time is rare — optimistic locking handles this gracefully without penalizing the common case.

3. **Better user experience.** When a conflict does occur, the user gets a clear, actionable message ("stale data, please refresh") instead of their browser hanging for 5 seconds waiting for a lock. Streamlit's form-based UI is request-response — users expect immediate feedback, not blocking waits.

4. **No deadlock risk.** Optimistic locking never holds database locks. Pessimistic locking (`SELECT FOR UPDATE`) can cause deadlocks if two transactions lock different rows in different orders. While `lock_timeout` mitigates this, it adds complexity.

5. **Streamlit connection model.** Streamlit caches connections with `@st.cache_resource(ttl=2700)`. Held locks from pessimistic locking could span multiple user sessions if the connection is reused, causing unexpected blocking. Optimistic locking avoids this entirely — each UPDATE is atomic and releases immediately.

6. **Network efficiency.** Optimistic locking does a single `UPDATE ... RETURNING` round-trip. Pessimistic locking requires two: `SELECT FOR UPDATE` then `UPDATE`. On Streamlit Cloud (which connects through Databricks SDK → Lakebase Postgres), minimizing round-trips is important for responsiveness.

7. **Scales to more users.** Optimistic locking has no contention — 100 users can read the same well simultaneously without any blocking. Only the rare write-conflict case triggers a retry. Pessimistic locking would serialize all writes to the same row, creating a bottleneck as user count grows.

8. **Future-proof.** If conflict rates increase (many users editing the same well), switching to pessimistic locking is straightforward — the API signature changes minimally (drop `previous_updated_at`, add `SELECT FOR UPDATE`). Both approaches are documented here for that transition.

### When to Switch to Pessimistic Locking (Future Trigger)

Consider switching to Approach 2 (pessimistic locking) if:

- Users frequently see "stale data" errors (conflict rate > 10% of write attempts)
- Multiple operators edit the same well's production rates simultaneously (e.g., real-time SCADA integration)
- The app adds features like collaborative editing or live-updating dashboards with write-back
- You need strict ordering of writes (e.g., audit trails requiring sequential updates)

To switch, replace the optimistic locking functions with the pessimistic locking versions (documented above) and remove the `previous_updated_at` parameter from the UI calls.

### Concurrency Protection Summary

| Operation | Protection | Mechanism |
|-----------|-----------|-----------|
| INSERT (add well) | Primary key constraint | `well_id` is PK — PostgreSQL rejects duplicates |
| UPDATE status | ✅ Optimistic locking | `WHERE well_id = %s AND updated_at = %s` + `RETURNING` check |
| UPDATE rates | ✅ Optimistic locking | `WHERE well_id = %s AND updated_at = %s` + `RETURNING` check |
| DELETE well | Row-level lock (implicit) | `DELETE` auto-locks the row during transaction |
| SELECT (all reads) | MVCC snapshot | Readers never blocked; see last committed version |
| Transaction safety | Commit/Rollback | `try-except` with `conn.rollback()` on all operations |

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
