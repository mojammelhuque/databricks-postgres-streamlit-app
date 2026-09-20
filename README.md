# 🛢️ Databricks Postgres Streamlit Apps

> **End-to-end workflow for testing Lakebase Postgres read/write with Streamlit apps** — synced from Unity Catalog to Lakebase Postgres using Reverse ETL.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Context](#data-context)
4. [Prerequisites](#prerequisites)
5. [Setup Guide](#setup-guide)
6. [Running the Streamlit App](#running-the-streamlit-app)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Data Dictionary](#data-dictionary)
9. [Troubleshooting](#troubleshooting)
10. [Security](#security)
11. [Documentation](#documentation)

---

## Overview

This project demonstrates a complete end-to-end workflow for building data-driven applications using **Databricks Lakebase Postgres** and **Streamlit**. The data domain is **Oil & Gas production**, chosen for its human-readable fields that make the data context easy to understand for anyone.

### What This Project Does

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          END-TO-END WORKFLOW                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. Unity Catalog (Delta Table)                                         │
│     └─ workspace.oil_gas_ops.well_production (25 wells, 8 basins)       │
│         ↓ Reverse ETL (Triggered sync)                                  │
│  2. Lakebase Postgres (databricks-postgres-streamlit project)            │
│     └─ Postgres table: synced_well_production                          │
│         ↓ Read/Write via psycopg / PostgREST Data API                   │
│  3. Streamlit App                                                        │
│     ├─ Read:  View production data, filter by basin/operator/status     │
│     ├─ Write: Update well status, add new wells, edit production rates  │
│     └─ Analytics: Charts, maps, summary statistics                     │
│         ↓ Deploy as                                                     │
│  4. Deploy to:                                                          │
│     • Databricks App (auto-credentials)                                 │
│     • Streamlit Community Cloud (✅ deployed, SDK token refresh)        │
│     • Local/RStudio (manual env vars)                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Technology | Purpose |
|-----------|-----------|----------|
| Source Data | Unity Catalog Delta Table | Oil & Gas well production data |
| Sync Pipeline | Lakeflow Spark Declarative Pipeline (Reverse ETL) | Triggered sync from UC → Postgres |
| Target Database | Lakebase Postgres | Managed OLTP Postgres with autoscaling |
| App Framework | Streamlit | Interactive web UI for read/write operations |
| Deployment | Databricks App + Local/RStudio | Hosted or standalone deployment |
| Connection | psycopg3 / PostgREST Data API | Direct SQL or HTTP CRUD API |

---

## Architecture

```
                          ┌──────────────────────┐
                          │   Unity Catalog      │
                          │  (Delta Lake Table)   │
                          │                      │
                          │ workspace.oil_gas_ops │
                          │ .well_production     │
                          │  (25 wells, 8 basins) │
                          └──────────┬───────────┘
                                     │
                              Reverse ETL (Triggered)
                              (CDF enabled, scheduled
                               updates via SDP pipeline)
                                     │
                          ┌──────────▼───────────┐
                          │  Lakebase Postgres    │
                          │  (Autoscaling)        │
                          │                      │
                          │ Project:             │
                          │ databricks-postgres-  │
                          │   streamlit           │
                          │                      │
                          │ Database:            │
                          │ databricks_postgres  │
                          │                      │
                          │ Table:               │
                          │ synced_well_         │
                          │   production         │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │   Connection Layer    │
                          │                      │
                          │  ┌──────┐  ┌───────┐ │
                          │  │psycopg│  │Data   │ │
                          │  │ (SQL) │  │API    │ │
                          │  │      │  │(HTTP) │ │
                          │  └──┬───┘  └───┬───┘ │
                          └─────┼─────────┼─────┘
                                │         │
                          ┌─────▼─────────▼─────┐
                          │   Streamlit App      │
                          │                      │
                          │  📊 Dashboard       │
                          │  📝 CRUD Operations  │
                          │  🗺️  Well Map        │
                          │  📈 Charts & Stats   │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │  Deployment Options  │
                          │                      │
                          │  ┌─────────┐         │
                          │  │Databricks│         │
                          │  │  Apps   │         │
                          │  │(hosted) │         │
                          │  └─────────┘         │
                          │  ┌─────────┐         │
                          │  │ Local /  │         │
                          │  │ RStudio  │         │
                          │  │(standalone)│       │
                          │  └─────────┘         │
                          └──────────────────────┘
```

---

## Data Context

### Oil & Gas Well Production Data

This project uses **realistic Oil & Gas production data** with human-readable fields. The data represents daily production readings from oil and gas wells across major US basins.

### Key Data Points

| Metric | Value |
|--------|-------|
| Total Wells | 25 |
| Basins | 8 (Permian, Eagle Ford, Bakken, Haynesville, Marcellus, Niobrara, Anadarko, Gulf of Mexico) |
| Operators | 17 (Pioneer, Chevron, ExxonMobil, BP, EOG, etc.) |
| Active Wells | 20 |
| Shut-in Wells | 2 |
| Maintenance Wells | 2 |
| Total Oil Production | ~34,223 bbl/day |
| Total Gas Production | ~66,221 Mcf/day |
| Average Water Cut | 16.35% |

### Sample Record

```
Well:       Permian Alpha #1
Operator:   Pioneer Natural Resources
Field:      Spraberry Trend
Basin:      Permian
Location:   Midland County, Texas
Oil Rate:   850.50 bbl/day
Gas Rate:   1,250.00 Mcf/day
Water Rate: 320.00 bbl/day
Gas Lift:   150.00 Mcf/day
Water Cut:  27.35%
Status:     ACTIVE
Date:       2026-09-15
```

---

## Prerequisites

### Databricks Workspace
- Databricks workspace with Lakebase Postgres enabled
- Unity Catalog with permission to create schemas and tables
- Databricks SDK for Python >= 0.118.0

### Local Development
- Python 3.10+
- pip (Python package installer)
- Git
- A Databricks account with access to Lakebase Postgres

### Databricks App Deployment
- Databricks Apps feature enabled in your workspace
- Git repository linked to your Databricks workspace

---

## Setup Guide

### Step 1: Create Lakebase Postgres Project

Run the setup notebook in Databricks (see `notebooks/setup_and_sync.py`):

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import Project, ProjectSpec

w = WorkspaceClient()
op = w.postgres.create_project(
    project=Project(spec=ProjectSpec(display_name="Databricks Postgres Streamlit", pg_version=17)),
    project_id="databricks-postgres-streamlit",
)
project = op.wait()
print("Created project:", project.name)
```

This auto-creates:
- `production` branch (READY state)
- `primary` read-write endpoint (ACTIVE state, scale-to-zero)
- `databricks_postgres` database

### Step 2: Create Unity Catalog Table

```sql
CREATE SCHEMA IF NOT EXISTS workspace.oil_gas_ops
COMMENT 'Oil & Gas operational data for Lakebase Postgres Streamlit testing';

CREATE TABLE workspace.oil_gas_ops.well_production (
  well_id BIGINT NOT NULL,
  well_name STRING NOT NULL,
  operator STRING NOT NULL,
  field_name STRING NOT NULL,
  basin STRING NOT NULL,
  state STRING NOT NULL,
  county STRING NOT NULL,
  api_number STRING,
  oil_rate DECIMAL(10,2),
  gas_rate DECIMAL(10,2),
  water_rate DECIMAL(10,2),
  gas_lift_rate DECIMAL(10,2),
  water_cut DECIMAL(5,2),
  well_status STRING NOT NULL,
  production_date DATE NOT NULL,
  latitude DECIMAL(10,6),
  longitude DECIMAL(10,6),
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');
```

### Step 3: Set Up Reverse ETL Sync

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import (
    SyncedTable, SyncedTableSyncedTableSpec,
    SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy,
)

w = WorkspaceClient()
op = w.postgres.create_synced_table(
    synced_table=SyncedTable(spec=SyncedTableSyncedTableSpec(
        source_table_full_name="workspace.oil_gas_ops.well_production",
        branch="projects/databricks-postgres-streamlit/branches/production",
        primary_key_columns=["well_id"],
        scheduling_policy=SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy.TRIGGERED,
        postgres_database="databricks_postgres",
        create_database_objects_if_missing=True,
    )),
    synced_table_id="workspace.oil_gas_ops.synced_well_production",
)
op.wait()
```

---

## Running the Streamlit App

### Option A: Databricks App (Hosted)

```bash
# From the Databricks CLI
databricks apps deploy oil-gas-streamlit-app
```

See `app/app.yaml` for the Databricks App configuration.

### Option B: Local Development

```bash
cd app/
pip install -r requirements.txt
streamlit run app.py
```

### Option C: RStudio / Posit Workbench

```bash
# In RStudio terminal
cd /path/to/databricks-postgres-streamlit-apps/app
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

### Option D: Streamlit Community Cloud (FREE)

**✅ Successfully Deployed**: September 20, 2026

[Streamlit Community Cloud](https://share.streamlit.io/) hosts your app for free with auto-deploy from GitHub. The app uses Databricks SDK to auto-generate fresh Lakebase tokens every 45 minutes.

**Quick Start:**

1. Go to [share.streamlit.io](https://share.streamlit.io/)
2. Connect your GitHub repo: `mojammelhuque/databricks-postgres-streamlit-app`
3. Set main file: `app/app.py`
4. Configure secrets (Settings → Secrets):

```toml
DATABRICKS_HOST = "https://dbc-050f2fd4-a450.cloud.databricks.com"
DATABRICKS_TOKEN = "dapiYOUR_TOKEN_HERE"
LAKEBASE_PG_HOST = "ep-patient-term-d801116u.database.us-east-2.cloud.databricks.com"
LAKEBASE_PG_USER = "your.email@example.com"
LAKEBASE_PG_DB = "databricks_postgres"
LAKEBASE_PG_PORT = "5432"
LAKEBASE_PROJECT = "databricks-postgres-streamlit"
LAKEBASE_BRANCH = "production"
```

5. Click "Deploy!" — app will be live at `https://your-app-name.streamlit.app`

**See full guide**: [docs/streamlit_cloud_deployment.md](docs/streamlit_cloud_deployment.md)

**Key Features:**
* ✅ Auto-deploy from GitHub (push to `main` → instant redeploy)
* ✅ Token auto-refresh every 45 minutes (no manual rotation)
* ✅ Free tier (no cost for public apps)
* ✅ Custom URL (`*.streamlit.app`)
* ⚠️ PAT expires every 90 days (manual renewal required)

**Issues Solved During Deployment:**
* Endpoint path format (missing branch segment)
* Schema mismatch (`public` vs `oil_gas_ops`)
* Transaction error handling (rollback on failures)

See [docs/streamlit_cloud_deployment.md](docs/streamlit_cloud_deployment.md) → "Deployment Success Log" for detailed troubleshooting.

---

## Data Dictionary

See [docs/data_dictionary.md](docs/data_dictionary.md) for the complete field-by-field description of all columns in the well_production table.

---

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues and solutions.

---

## Security

See [docs/security.md](docs/security.md) for the full security architecture, credential management, and compliance documentation.

Key highlights:
* No secrets in version control (verified by CI scan)
* OAuth tokens auto-rotate every 60 minutes
* SSL/TLS encryption on all connections
* VPC-isolated database endpoint

---

## Documentation

| Document | Description |
|----------|-------------|
| [architecture.md](docs/architecture.md) | System architecture, data flow, and security model |
| [data_dictionary.md](docs/data_dictionary.md) | Field-by-field data dictionary |
| [deployment_guide.md](docs/deployment_guide.md) | Step-by-step deployment for Databricks Apps, local, and RStudio |
| [api_reference.md](docs/api_reference.md) | Function reference for app.py |
| [security.md](docs/security.md) | Security architecture, credentials, and compliance |
| [branching_strategy.md](docs/branching_strategy.md) | Git branching, CI/CD pipeline, and developer workflow |
| [troubleshooting.md](docs/troubleshooting.md) | Common issues, error messages, and solutions |

---

## CI/CD Pipeline

This project uses GitHub Actions for continuous integration and deployment.

### Pipeline Overview

```
Feature Branch  ->  Dev Branch  ->  Main Branch  ->  Production
   (develop)        (testing)      (review)        (deploy)
```

### CI Stage (on push to `dev` or PR to `main`)

1. **Lint with flake8** - Syntax and code quality checks
2. **Validate imports** - Verify required Python modules are imported
3. **Validate app.yaml** - Check YAML structure and required keys
4. **Secret scan** - Detect hardcoded passwords/tokens/secrets

### CD Stage (on PR merge to `main`)

1. Install Databricks CLI
2. Configure with GitHub Secrets
3. Deploy app to Databricks Apps
4. Generate deployment summary

### Required GitHub Secrets

| Secret | Description |
|-------|-------------|
| `DATABRICKS_HOST` | Your Databricks workspace URL |
| `DATABRICKS_TOKEN` | Databricks personal access token |
| `DATABRICKS_APP_NAME` | Name of the Databricks App |

See [docs/branching_strategy.md](docs/branching_strategy.md) for the full branching workflow.

---

## Repository Structure

```
databricks-postgres-streamlit-apps/
├── README.md                        # This file - project overview and setup guide
├── .gitignore                        # Git ignore rules (.env, etc.)
├── app/                              # Streamlit application
│   ├── app.py                        # Main Streamlit app (read/write to Postgres)
│   ├── app.yaml                      # Databricks App configuration
│   └── requirements.txt              # Python dependencies
├── notebooks/                        # Setup and configuration
│   └── setup_and_sync.py             # Notebook to create project, table, and sync
├── .github/                          # CI/CD configuration
│   ├── workflows/
│   │   └── ci-cd.yml                 # GitHub Actions CI/CD pipeline
│   └── pull_request_template.md      # PR template
└── docs/                             # Documentation
    ├── architecture.md               # System architecture and data flow
    ├── data_dictionary.md            # Field descriptions for Oil & Gas data
    ├── deployment_guide.md            # Step-by-step deployment instructions
    ├── api_reference.md              # Function reference for app.py
    ├── security.md                    # Security architecture and best practices
    ├── branching_strategy.md          # Git branching and CI/CD workflow
    └── troubleshooting.md            # Common issues and solutions
```

---

## License

This project is for testing and educational purposes.

---

## Author

Mojammel Huque — [GitHub](https://github.com/mojammelhuque)