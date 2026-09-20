# 🏗️ Architecture - Databricks Postgres Streamlit Apps

> Detailed system architecture and data flow documentation.

---

## System Overview

This project implements a **3-tier architecture** for Oil & Gas production data:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             TIER 1: DATA SOURCE                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Unity Catalog (Delta Lake)                                         │    │
│  │                                                                     │    │
│  │  Catalog: workspace                                                 │    │
│  │  Schema:  oil_gas_ops                                                │    │
│  │  Table:   well_production                                            │    │
│  │                                                                     │    │
│  │  Features:                                                          │    │
│  │  • Delta Lake with ACID transactions                                │    │
│  │  • Change Data Feed (CDF) enabled                                   │    │
│  │  • 25 wells across 8 US basins                                      │    │
│  │  • Human-readable Oil & Gas production fields                       │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                 │                                            │
│                     Reverse ETL (Triggered)                                  │
│                     via Lakeflow Spark Declarative Pipeline                  │
└─────────────────────────────────┼────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TIER 2: POSTGRES DATABASE                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Lakebase Postgres (Autoscaling)                                    │    │
│  │                                                                     │    │
│  │  Project:     databricks-postgres-streamlit                         │    │
│  │  Branch:      production (copy-on-write)                            │    │
│  │  Endpoint:    primary (read-write, scale-to-zero)                   │    │
│  │  Database:    databricks_postgres                                   │    │
│  │  Table:       synced_well_production                                │    │
│  │                                                                     │    │
│  │  Features:                                                          │    │
│  │  • Serverless Postgres with autoscaling (0.5-32 CU)                │    │
│  │  • Scale-to-zero after 5 min idle                                   │    │
│  │  • PostgREST-compatible Data API (HTTP CRUD)                       │    │
│  │  • OAuth token authentication (1-hour expiry)                       │    │
│  │  • Branching for dev/test environments                             │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                 │                                            │
└─────────────────────────────────┼────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TIER 3: APPLICATION LAYER                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Streamlit App                                                      │    │
│  │                                                                     │    │
│  │  Pages:                                                             │    │
│  │  • Dashboard  - KPIs, charts, status overview                      │    │
│  │  • Well List  - Filterable data table                               │    │
│  │  • Add Well   - INSERT form                                         │    │
│  │  • Edit Well   - UPDATE status/rates                               │    │
│  │  • Delete Well - DELETE with confirmation                          │    │
│  │  • Analytics  - Charts, maps, scatter plots                       │    │
│  │                                                                     │    │
│  │  Connection: psycopg3 (SQL) or PostgREST Data API (HTTP)           │    │
│  └──────────────────────────────┬──────────────────────────────────────┘    │
│                                 │                                            │
│                    ┌────────────┴────────────┐                               │
│                    ▼                         ▼                               │
│           Databricks App              Local / RStudio                      │
│           (Hosted, auto-config)      (Standalone, env vars)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Source: Unity Catalog Delta Table

```
workspace.oil_gas_ops.well_production
├── 25 rows of Oil & Gas well production data
├── CDF enabled for incremental sync
├── Primary key: well_id
└── TBLPROPERTIES: delta.enableChangeDataFeed = true
```

### 2. Sync: Reverse ETL (Triggered Mode)

```
Pipeline: Lakeflow Spark Declarative Pipeline
├── Mode: Triggered (scheduled updates)
├── Source: workspace.oil_gas_ops.well_production
├── Target: databricks_postgres.public.synced_well_production
├── Primary key: well_id
├── CDF required: Yes (enabled on source table)
└── Sync rate: ~150 rows/sec per CU
```

**Sync Modes Available:**

| Mode | Latency | CDF Required | Use Case |
|------|---------|-------------|----------|
| Snapshot | One-time | No | Initial setup, bulk loads |
| Triggered | Scheduled | Yes | Dashboards, hourly/daily updates |
| Continuous | Seconds | Yes | Real-time applications |

### 3. Target: Lakebase Postgres

```
Project: databricks-postgres-streamlit
├── Branch: production (READY)
├── Endpoint: primary (ACTIVE, scale-to-zero)
│   └── Host: ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com
├── Database: databricks_postgres
├── Table: synced_well_production (in public schema)
└── Features:
    ├── PostgREST Data API (HTTP CRUD)
    ├── OAuth token auth (1-hour expiry)
    ├── Connection pooling (psycopg3)
    └── Branching for dev/test
```

### 4. Application: Streamlit

```
Connection Methods:
├── Direct SQL (psycopg3)
│   ├── Host: from endpoint
│   ├── User: Databricks email
│   ├── Password: OAuth token (refreshed every 45 min)
│   ├── SSL: required
│   └── Pool: pool_pre_ping=True, pool_recycle=2700
└── PostgREST Data API (HTTP)
    ├── URL: from Data API settings
    ├── Auth: Bearer token
    └── CRUD: GET, POST, PATCH, DELETE
```

---

## Deployment Options

### Option A: Databricks App (Hosted)

```
┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│ Databricks   │    │  Lakebase     │    │  Streamlit   │
│  Apps        │───▶│  Postgres     │───▶│  UI          │
│              │    │               │    │              │
│ • Auto-auth  │    │ • OAuth       │    │ • Read data  │
│ • app.yaml   │    │   token       │    │ • Write data │
│ • Scalable   │    │   injection   │    │ • Charts     │
└──────────────┘    └───────────────┘    └──────────────┘
```

**Advantages:**
- Zero-config connection (auto-injected env vars)
- Managed scaling and SSL
- Built-in OAuth token rotation
- Direct access to Lakebase Postgres

### Option B: Local / RStudio (Standalone)

```
┌──────────────┐    ┌───────────────┐    ┌──────────────┐
│ Local /      │    │  Lakebase     │    │  Streamlit   │
│ RStudio      │───▶│  Postgres     │───▶│  UI          │
│              │    │               │    │              │
│ • Env vars   │    │ • OAuth       │    │ • Read data  │
│ • Manual     │    │   token       │    │ • Write data │
│   config     │    │   (manual)    │    │ • Charts     │
└──────────────┘    └───────────────┘    └──────────────┘
```

**Configuration:**
```bash
export LAKEBASE_PG_HOST=your-endpoint-host
export LAKEBASE_PG_USER=your-email@company.com
export LAKEBASE_PG_PASSWORD=your-oauth-token
export LAKEBASE_PG_DB=databricks_postgres
```

---

## Security Model

```
┌─────────────────────────────────────────────────┐
│                 Security Layers                   │
├─────────────────────────────────────────────────┤
│                                                  │
│  1. Unity Catalog                                │
│     └─ Table-level permissions (SELECT, MODIFY)  │
│                                                  │
│  2. Lakebase Postgres                            │
│     └─ OAuth token (1-hour expiry, auto-refresh) │
│     └─ SSL/TLS required on all connections       │
│     └─ Role-based access (Postgres roles)        │
│                                                  │
│  3. Databricks App                               │
│     └─ Service Principal (CAN_CONNECT_AND_CREATE)│
│     └─ Auto-injected connection credentials     │
│                                                  │
│  4. PostgREST Data API (optional)                │
│     └─ Bearer token authentication               │
│     └─ Row-Level Security (RLS) policies         │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Resource Inventory

| Resource | Name | Type |
|----------|------|------|
| UC Schema | workspace.oil_gas_ops | Schema |
| UC Table | workspace.oil_gas_ops.well_production | Delta Table |
| Synced Table | workspace.oil_gas_ops.synced_well_production | Synced Table |
| Lakebase Project | databricks-postgres-streamlit | Postgres Project |
| Lakebase Branch | production | Branch |
| Lakebase Endpoint | primary | Read-Write Endpoint |
| Lakebase Database | databricks_postgres | Database |
| Sync Pipeline | a41bf65e-3ca8-4522-aebf-e196234fd973 | SDP Pipeline |
| GitHub Repo | databricks-postgres-streamlit-app | Git Repository |

---

## CI/CD Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CI/CD PIPELINE ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────┐     ┌────────────┐     ┌────────────┐              │
│  │  Feature   │ PR  │    Dev     │ PR  │   Main     │              │
│  │  Branch    │──→ │  (Testing) │──→ │(Production)│              │
│  │ feature/*  │     │            │     │            │              │
│  └────────────┘     └────────────┘     └────────────┘              │
│                            │                    │                  │
│                     CI Pipeline            CD Pipeline              │
│                     (on push/PR)          (on merge)                │
│                            │                    │                  │
│                     ┌──────┴──────┐     ┌──────┴──────┐           │
│                     │ 1. Lint     │     │ 1. Checkout │           │
│                     │ 2. Imports  │     │ 2. Python   │           │
│                     │ 3. YAML val │     │ 3. CLI setup│           │
│                     │ 4. Secret   │     │ 4. Configure│           │
│                     │    scan    │     │ 5. Deploy  │           │
│                     └─────────────┘     │ 6. Summary │           │
│                                          └────────────┘           │
│                                                                     │
│  GitHub Secrets: DATABRICKS_HOST, DATABRICKS_TOKEN,               │
│                  DATABRICKS_APP_NAME                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### CI Pipeline Stages

| Stage | Tool | Purpose | Blocking |
|-------|------|---------|----------|
| Lint | flake8 | Syntax errors, code quality | Yes |
| Import Validation | ast module | Required modules imported | Yes |
| YAML Validation | PyYAML | app.yaml structure and keys | Yes |
| Secret Scan | grep (POSIX) | Hardcoded credentials | Yes |

### CD Pipeline Stages

| Stage | Tool | Purpose |
|-------|------|---------|
| Checkout | actions/checkout@v4 | Get source code |
| Python Setup | actions/setup-python@v5 | Python 3.11 |
| CLI Install | curl + install.sh | Databricks CLI |
| Configure | GitHub Secrets | DATABRICKS_HOST/TOKEN |
| Deploy | databricks apps deploy | Deploy to Databricks Apps |
| Summary | $GITHUB_STEP_SUMMARY | Deployment record |

---

## Deployment Architecture

### Databricks Apps (Production)

```
GitHub Actions CI/CD
        │
        ▼
databricks apps deploy --source-path ./app
        │
        ▼
┌───────────────────────────────────────────────┐
│  Databricks App (oil-gas-streamlit-app)        │
│  ┌───────────────────────────────────────────┐│
│  │  Streamlit Runtime                        ││
│  │  • Python 3.11                            ││
│  │  • Auto-scaled compute                    ││
│  │  • Auto-injected Lakebase credentials     ││
│  └──────────────────┬────────────────────────┘│
│                     │                          │
│  ┌──────────────────▼────────────────────────┐│
│  │  Lakebase Postgres Connection              ││
│  │  • OAuth token (auto-rotated hourly)      ││
│  │  • SSL/TLS encrypted                       ││
│  │  • Connection cached (45 min TTL)          ││
│  └──────────────────┬────────────────────────┘│
└─────────────────────┼─────────────────────────┘
                      │
                      ▼
              Lakebase Postgres
              (production branch)
```

### Local Development

```
Developer Machine
├── .env file (git-ignored)
│   ├── LAKEBASE_PG_HOST
│   ├── LAKEBASE_PG_USER
│   └── LAKEBASE_PG_PASSWORD (manual OAuth token)
│
├── streamlit run app.py
│   └── python-dotenv loads .env
│
└── Direct SSL connection to Lakebase Postgres
```