# 📖 API Reference - Oil & Gas Streamlit App

> Complete function reference for `app/app.py` with parameters, return types, and usage examples.

---

## Table of Contents

1. [Configuration](#configuration)
2. [Database Connection](#database-connection)
3. [Query Execution](#query-execution)
4. [Data Operations (CRUD)](#data-operations-crud)
5. [Streamlit UI Pages](#streamlit-ui-pages)

---

## Configuration

### `DEFAULT_CONFIG`

Default database configuration dictionary populated from environment variables.

| Key | Type | Source | Default |
|-----|------|--------|---------|
| `host` | `str` | `LAKEBASE_PG_HOST` | `""` |
| `database` | `str` | `LAKEBASE_PG_DB` | `"databricks_postgres"` |
| `user` | `str` | `LAKEBASE_PG_USER` | `""` |
| `password` | `str` | `LAKEBASE_PG_PASSWORD` | `""` |
| `port` | `int` | `LAKEBASE_PG_PORT` | `5432` |

### `TABLE_NAME`

```python
TABLE_NAME = "synced_well_production"
```

The Postgres table name for synced well production data.

### `SCHEMA_NAME`

```python
SCHEMA_NAME = "public"
```

The Postgres schema where the synced table resides.

---

## Database Connection

### `get_connection()`

Creates and caches a connection to Lakebase Postgres.

```python
@st.cache_resource(ttl=2700)  # Cache for 45 minutes
def get_connection():
    ...
```

**Parameters**: None (reads from environment variables)

**Returns**: `psycopg.Connection` or `None`

**Behavior**:
1. If `DATABRICKS_LAKEBASE_PG_HOST` is set (Databricks Apps), uses auto-injected credentials
2. If `LAKEBASE_PG_URL` is set (local dev), connects via URL string
3. Otherwise, uses individual environment variables (`LAKEBASE_PG_HOST`, etc.)
4. Returns `None` and displays error if credentials are missing

**Cache**: TTL of 2700 seconds (45 minutes) to refresh before 1-hour token expiry

**Example**:
```python
conn = get_connection()
if conn is None:
    st.stop()
```

---

## Query Execution

### `execute_query(conn, query, params=None, fetch=True)`

Executes a SQL query with optional parameterized inputs.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |
| `query` | `str` | Yes | SQL query string (use `%s` placeholders) |
| `params` | `tuple` | No | Parameter values for query placeholders |
| `fetch` | `bool` | No | If `True`, returns results; if `False`, commits and returns `None` |

**Returns**:
- If `fetch=True`: `(columns: list[str], rows: list[tuple])`
- If `fetch=False`: `(None, None)`

**Example**:
```python
# SELECT
columns, rows = execute_query(conn, "SELECT * FROM wells WHERE status = %s", ("ACTIVE",))

# INSERT/UPDATE/DELETE
execute_query(conn, "INSERT INTO wells (id) VALUES (%s)", (1,), fetch=False)
```

---

### `fetch_dataframe(conn, query, params=None)`

Executes a query and returns results as a pandas DataFrame.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |
| `query` | `str` | Yes | SQL query string |
| `params` | `tuple` | No | Parameter values |

**Returns**: `pd.DataFrame` (empty if no rows)

**Side Effects**: Converts `Decimal` columns to `float` for display compatibility.

**Example**:
```python
df = fetch_dataframe(conn, "SELECT * FROM public.synced_well_production")
print(df.shape)  # (25, 19)
```

---

## Data Operations (CRUD)

### `get_all_wells(conn)`

Fetches all well production records from the database.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |

**Returns**: `pd.DataFrame` with columns: `well_id`, `well_name`, `operator`, `field_name`, `basin`, `state`, `county`, `api_number`, `oil_rate`, `gas_rate`, `water_rate`, `gas_lift_rate`, `water_cut`, `well_status`, `production_date`, `latitude`, `longitude`, `created_at`, `updated_at`

**Example**:
```python
df = get_all_wells(conn)
print(f"Total wells: {len(df)}")  # Total wells: 25
```

---

### `get_well_by_id(conn, well_id)`

Fetches a single well record by its ID.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |
| `well_id` | `int` | Yes | Unique well identifier |

**Returns**: `dict` (column name to value) or `None` if not found

**Example**:
```python
well = get_well_by_id(conn, 1)
print(well['well_name'])  # Permian Alpha #1
```

---

### `insert_well(conn, data)`

Inserts a new well production record.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |
| `data` | `dict` | Yes | Well data dictionary (see below) |

**Required `data` keys**: `well_id`, `well_name`, `operator`, `field_name`, `basin`, `state`, `county`, `well_status`, `production_date`

**Optional `data` keys** (default 0/None): `api_number`, `oil_rate`, `gas_rate`, `water_rate`, `gas_lift_rate`, `water_cut`, `latitude`, `longitude`

**Auto-set fields**: `created_at`, `updated_at` (set to `datetime.now()`)

**Returns**: `None` (commits transaction)

**Example**:
```python
insert_well(conn, {
    'well_id': 26,
    'well_name': 'Permian Alpha #26',
    'operator': 'Pioneer Natural Resources',
    'field_name': 'Spraberry Trend',
    'basin': 'Permian',
    'state': 'Texas',
    'county': 'Midland',
    'well_status': 'ACTIVE',
    'production_date': date(2026, 9, 20),
    'oil_rate': 500.0,
    'gas_rate': 800.0,
})
```

---

### `update_well_status(conn, well_id, new_status)`

Updates a well's operational status.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |
| `well_id` | `int` | Yes | Well ID to update |
| `new_status` | `str` | Yes | New status: `ACTIVE`, `SHUT_IN`, `MAINTENANCE`, or `COMPLETED` |

**Returns**: `None` (commits transaction)

**Example**:
```python
update_well_status(conn, well_id=5, new_status='MAINTENANCE')
```

---

### `update_well_rates(conn, well_id, oil_rate, gas_rate, water_rate, gas_lift_rate, water_cut)`

Updates a well's production rates.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |
| `well_id` | `int` | Yes | Well ID to update |
| `oil_rate` | `float` | Yes | Oil production rate (bbl/day) |
| `gas_rate` | `float` | Yes | Gas production rate (Mcf/day) |
| `water_rate` | `float` | Yes | Water production rate (bbl/day) |
| `gas_lift_rate` | `float` | Yes | Gas lift injection rate (Mcf/day) |
| `water_cut` | `float` | Yes | Water cut percentage (0-100) |

**Returns**: `None` (commits transaction)

**Example**:
```python
update_well_rates(conn, well_id=1, oil_rate=900.0, gas_rate=1400.0,
                  water_rate=350.0, gas_lift_rate=160.0, water_cut=28.0)
```

---

### `delete_well(conn, well_id)`

Deletes a well production record.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `conn` | `psycopg.Connection` | Yes | Active database connection |
| `well_id` | `int` | Yes | Well ID to delete |

**Returns**: `None` (commits transaction)

**Example**:
```python
delete_well(conn, well_id=26)
```

---

## Streamlit UI Pages

### `main()`

Main entry point for the Streamlit application. Renders all pages and handles navigation.

**Pages**:

| Page | Icon | Description |
|------|------|-------------|
| Dashboard | 📊 | KPI cards (total wells, active wells, oil/gas totals), oil/gas by basin bar charts, well status pie chart |
| Well List | 📋 | Filterable data table with basin, operator, and status filters |
| Add New Well | ➕ | Form to insert new well records with validation |
| Edit Well | ✏️ | Update well status and production rates |
| Delete Well | 🗑️ | Delete well records with confirmation dialog |
| Analytics | 📈 | Scatter plots, well location map, production trend analysis |

**Sidebar Features**:
- Connection status indicator
- Page navigation (radio buttons)
- Database connection info display

---

## Environment Variables Reference

### Databricks Apps (Auto-Injected)

| Variable | Description |
|----------|-------------|
| `DATABRICKS_LAKEBASE_PG_HOST` | Postgres endpoint hostname |
| `DATABRICKS_LAKEBASE_PG_PORT` | Postgres port (5432) |
| `DATABRICKS_LAKEBASE_PG_USER` | Databricks user email |
| `DATABRICKS_LAKEBASE_PG_PASSWORD` | OAuth token (auto-rotated) |
| `DATABRICKS_LAKEBASE_PG_DATABASE` | Database name |

### Local Development (Manual)

| Variable | Description | Required |
|----------|-------------|----------|
| `LAKEBASE_PG_HOST` | Postgres endpoint hostname | Yes* |
| `LAKEBASE_PG_PORT` | Postgres port | No (default: 5432) |
| `LAKEBASE_PG_USER` | Databricks user email | Yes* |
| `LAKEBASE_PG_PASSWORD` | OAuth token | Yes* |
| `LAKEBASE_PG_DB` | Database name | No (default: databricks_postgres) |
| `LAKEBASE_PG_URL` | Full connection URL (overrides individual vars) | Alternative to above |

\* Required unless `LAKEBASE_PG_URL` is provided.

---

## App Configuration (app.yaml)

| Key | Value | Description |
|-----|-------|-------------|
| `entrypoint` | `app/app.py` | Main Streamlit app file |
| `python_version` | `"3.11"` | Python runtime version |
| `lakebase.postgres.project` | `databricks-postgres-streamlit` | Lakebase project name |
| `lakebase.postgres.branch` | `production` | Lakebase branch |
| `lakebase.postgres.database` | `databricks_postgres` | Postgres database name |
| `env[APP_TITLE]` | `"Oil & Gas Well Production Dashboard"` | App display title |
| `env[TABLE_NAME]` | `"synced_well_production"` | Postgres table name |
| `env[SCHEMA_NAME]` | `"public"` | Postgres schema name |