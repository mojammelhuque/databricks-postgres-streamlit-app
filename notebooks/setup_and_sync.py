# ============================================================================
# Oil & Gas Streamlit Apps - Setup & Sync Notebook
# ============================================================================
# This notebook sets up the entire end-to-end workflow:
#   1. Upgrades the Databricks SDK
#   2. Creates the Lakebase Postgres project
#   3. Creates the Unity Catalog schema and table with sample data
#   4. Enables Change Data Feed (CDF)
#   5. Sets up Reverse ETL sync (Triggered mode) from UC -> Postgres
#   6. Verifies the sync status
# ============================================================================

# ---------------------------------------------------------------------------
# Cell 1: Upgrade Databricks SDK
# ---------------------------------------------------------------------------
import importlib.metadata as md
import subprocess, sys

try:
    before = md.version("databricks-sdk")
except md.PackageNotFoundError:
    before = None

subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "databricks-sdk>=0.118.0"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

after = md.version("databricks-sdk")
print(f"databricks-sdk: {before} -> {after}  (changed={before != after})")

if before != after:
    print("Version changed \u2014 restarting Python to load the new SDK...")
    dbutils.library.restartPython()

# ---------------------------------------------------------------------------
# Cell 2: Create Lakebase Postgres Project
# ---------------------------------------------------------------------------
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import Project, ProjectSpec

w = WorkspaceClient()

PROJECT_ID = "databricks-postgres-streamlit"
DISPLAY_NAME = "Databricks Postgres Streamlit"

op = w.postgres.create_project(
    project=Project(spec=ProjectSpec(display_name=DISPLAY_NAME, pg_version=17)),
    project_id=PROJECT_ID,
)
project = op.wait()
print(f"Created project: {project.name}")
print(f"Display name: {project.spec.display_name}")

# Verify branches and endpoints
print("\n=== Branches ===")
for b in w.postgres.list_branches(parent=f"projects/{PROJECT_ID}"):
    print(f"  Branch: {b.name}  State: {b.status.current_state}")

print("\n=== Endpoints ===")
for e in w.postgres.list_endpoints(parent=f"projects/{PROJECT_ID}/branches/production"):
    print(f"  Endpoint: {e.name}")
    if e.status:
        print(f"  State: {e.status.current_state}")
        if e.status.hosts and e.status.hosts.host:
            print(f"  Host: {e.status.hosts.host}")

print("\n=== Databases ===")
for d in w.postgres.list_databases(parent=f"projects/{PROJECT_ID}/branches/production"):
    print(f"  Database: {d.name}")

# ---------------------------------------------------------------------------
# Cell 3: Create Unity Catalog Schema and Table
# ---------------------------------------------------------------------------
# Create schema
spark.sql("""
CREATE SCHEMA IF NOT EXISTS workspace.oil_gas_ops
COMMENT 'Oil & Gas operational data for Lakebase Postgres Streamlit testing'
""")
print("Schema created: workspace.oil_gas_ops")

# Create table with CDF enabled
spark.sql("""
CREATE TABLE IF NOT EXISTS workspace.oil_gas_ops.well_production (
  well_id BIGINT NOT NULL COMMENT 'Unique numeric identifier for each well',
  well_name STRING NOT NULL COMMENT 'Human-readable well name',
  operator STRING NOT NULL COMMENT 'Company operating the well',
  field_name STRING NOT NULL COMMENT 'Name of the oil/gas field',
  basin STRING NOT NULL COMMENT 'Geological basin',
  state STRING NOT NULL COMMENT 'US state',
  county STRING NOT NULL COMMENT 'County within the state',
  api_number STRING COMMENT 'API well identification number',
  oil_rate DECIMAL(10,2) COMMENT 'Oil production rate (bbl/day)',
  gas_rate DECIMAL(10,2) COMMENT 'Gas production rate (Mcf/day)',
  water_rate DECIMAL(10,2) COMMENT 'Water production rate (bbl/day)',
  gas_lift_rate DECIMAL(10,2) COMMENT 'Gas lift injection rate (Mcf/day)',
  water_cut DECIMAL(5,2) COMMENT 'Water cut percentage (0-100)',
  well_status STRING NOT NULL COMMENT 'Current status',
  production_date DATE NOT NULL COMMENT 'Date of production reading',
  latitude DECIMAL(10,6) COMMENT 'Well surface latitude',
  longitude DECIMAL(10,6) COMMENT 'Well surface longitude',
  created_at TIMESTAMP NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP NOT NULL COMMENT 'Record last update timestamp'
)
COMMENT 'Oil & Gas well production data'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")
print("Table created: workspace.oil_gas_ops.well_production (CDF enabled)")

# Insert sample data
spark.sql("""
INSERT INTO workspace.oil_gas_ops.well_production VALUES
  (1, 'Permian Alpha #1', 'Pioneer Natural Resources', 'Spraberry Trend', 'Permian', 'Texas', 'Midland', '42-329-10001', 850.50, 1250.00, 320.00, 150.00, 27.35, 'ACTIVE', DATE '2026-09-15', 31.845678, -102.078910, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (2, 'Permian Beta #2', 'Pioneer Natural Resources', 'Wolfcamp Shale', 'Permian', 'Texas', 'Midland', '42-329-10002', 1200.75, 2100.50, 480.00, 0.00, 28.57, 'ACTIVE', DATE '2026-09-15', 31.845700, -102.078950, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (3, 'Permian Gamma #3', 'Chevron', 'Bone Spring', 'Permian', 'Texas', 'Reeves', '42-329-10003', 650.25, 980.00, 150.00, 75.00, 18.75, 'ACTIVE', DATE '2026-09-15', 31.820000, -103.200000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (4, 'Permian Delta #4', 'ExxonMobil', 'Wolfcamp Shale', 'Permian', 'Texas', 'Loving', '42-329-10004', 0.00, 0.00, 0.00, 0.00, 0.00, 'SHUT_IN', DATE '2026-09-15', 31.850000, -103.250000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (5, 'Permian Epsilon #5', 'ConocoPhillips', 'Spraberry Trend', 'Permian', 'Texas', 'Midland', '42-329-10005', 950.00, 1450.25, 410.00, 200.00, 30.14, 'ACTIVE', DATE '2026-09-15', 31.845700, -102.079000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (6, 'Eagle Ford #12', 'EOG Resources', 'Eagle Ford Shale', 'Eagle Ford', 'Texas', 'Karnes', '42-255-20001', 720.50, 1850.00, 290.00, 0.00, 28.71, 'ACTIVE', DATE '2026-09-15', 28.850000, -97.850000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (7, 'Eagle Ford #15', 'EOG Resources', 'Eagle Ford Shale', 'Eagle Ford', 'Texas', 'DeWitt', '42-255-20002', 580.25, 1420.00, 210.00, 0.00, 26.58, 'ACTIVE', DATE '2026-09-15', 29.120000, -97.300000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (8, 'Eagle Ford #18', 'BHP Billiton', 'Eagle Ford Shale', 'Eagle Ford', 'Texas', 'McMullen', '42-255-20003', 420.00, 890.00, 95.00, 50.00, 18.42, 'MAINTENANCE', DATE '2026-09-15', 28.250000, -98.200000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (9, 'Bakken Drift #7', 'Continental Resources', 'Bakken Shale', 'Bakken', 'North Dakota', 'Mountrail', '33-061-30001', 680.00, 950.00, 180.00, 0.00, 20.93, 'ACTIVE', DATE '2026-09-15', 48.350000, -101.400000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (10, 'Bakken Prairie #3', 'Continental Resources', 'Three Forks', 'Bakken', 'North Dakota', 'Dunn', '33-061-30002', 540.50, 720.00, 130.00, 0.00, 19.40, 'ACTIVE', DATE '2026-09-15', 47.350000, -101.500000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (11, 'Bakken Horizon #9', 'Hess Corporation', 'Bakken Shale', 'Bakken', 'North Dakota', 'Williams', '33-061-30003', 0.00, 0.00, 0.00, 0.00, 0.00, 'COMPLETED', DATE '2026-09-15', 48.200000, -101.600000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (12, 'Haynesville Gas #1', 'Chesapeake Energy', 'Haynesville Shale', 'Haynesville', 'Louisiana', 'DeSoto', '22-031-40001', 0.00, 8500.00, 25.00, 0.00, 0.29, 'ACTIVE', DATE '2026-09-15', 32.100000, -93.700000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (13, 'Haynesville Gas #4', 'Comstock Resources', 'Haynesville Shale', 'Haynesville', 'Louisiana', 'Caddo', '22-017-40002', 0.00, 7200.00, 18.00, 0.00, 0.25, 'ACTIVE', DATE '2026-09-15', 32.500000, -93.900000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (14, 'Marcellus NE #2', 'Range Resources', 'Marcellus Shale', 'Marcellus', 'Pennsylvania', 'Washington', '42-125-50001', 0.00, 6200.00, 30.00, 0.00, 0.48, 'ACTIVE', DATE '2026-09-15', 40.200000, -80.250000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (15, 'Marcellus SW #5', 'EQT Corporation', 'Marcellus Shale', 'Marcellus', 'Pennsylvania', 'Greene', '42-059-50002', 0.00, 5800.00, 22.00, 0.00, 0.38, 'ACTIVE', DATE '2026-09-15', 39.900000, -80.100000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (16, 'Permian NM #8', 'Occidental Petroleum', 'Bone Spring', 'Permian', 'New Mexico', 'Eddy', '30-015-60001', 1100.00, 1800.00, 390.00, 120.00, 26.17, 'ACTIVE', DATE '2026-09-15', 32.300000, -104.200000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (17, 'Permian NM #11', 'Occidental Petroleum', 'Wolfcamp Shale', 'Permian', 'New Mexico', 'Lea', '30-025-60002', 880.50, 1350.00, 280.00, 0.00, 24.13, 'ACTIVE', DATE '2026-09-15', 32.700000, -103.500000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (18, 'Permian NM #14', 'Devon Energy', 'Bone Spring', 'Permian', 'New Mexico', 'Eddy', '30-015-60003', 320.00, 540.00, 85.00, 60.00, 20.98, 'MAINTENANCE', DATE '2026-09-15', 32.350000, -104.300000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (19, 'GOM Thunder Horse #1', 'BP', 'Thunder Horse Field', 'Gulf of Mexico', 'Louisiana', 'Plaquemines', 'offshore-001', 15000.00, 12000.00, 2500.00, 0.00, 14.29, 'ACTIVE', DATE '2026-09-15', 28.700000, -88.500000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (20, 'GOM Atlantis #2', 'BP', 'Atlantis Field', 'Gulf of Mexico', 'Louisiana', 'Plaquemines', 'offshore-002', 8200.00, 7500.00, 1200.00, 0.00, 12.76, 'ACTIVE', DATE '2026-09-15', 28.600000, -88.400000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (21, 'Niobrara Wattenberg #6', 'Noble Energy', 'Wattenberg Field', 'Niobrara', 'Colorado', 'Weld', '05-123-70001', 450.00, 820.00, 110.00, 0.00, 19.64, 'ACTIVE', DATE '2026-09-15', 40.400000, -104.700000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (22, 'Niobrara Wattenberg #9', 'Noble Energy', 'Wattenberg Field', 'Niobrara', 'Colorado', 'Weld', '05-123-70002', 380.00, 650.00, 85.00, 0.00, 18.28, 'ACTIVE', DATE '2026-09-15', 40.450000, -104.650000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (23, 'Anadarko SCOOP #3', 'Continental Resources', 'SCOOP Stack', 'Anadarko', 'Oklahoma', 'Grady', '40-049-80001', 520.00, 1100.00, 140.00, 80.00, 21.21, 'ACTIVE', DATE '2026-09-15', 35.000000, -97.900000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (24, 'Anadarko STACK #7', 'Devon Energy', 'STACK Field', 'Anadarko', 'Oklahoma', 'Canadian', '40-015-80002', 0.00, 0.00, 0.00, 0.00, 0.00, 'SHUT_IN', DATE '2026-09-15', 35.500000, -98.000000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00'),
  (25, 'Permian Zeta #10', 'Diamondback Energy', 'Wolfcamp Shale', 'Permian', 'Texas', 'Martin', '42-317-10006', 780.00, 1150.00, 350.00, 100.00, 30.97, 'ACTIVE', DATE '2026-09-15', 32.250000, -101.800000, TIMESTAMP '2026-09-15 06:00:00', TIMESTAMP '2026-09-15 06:00:00')
""")
print("25 well production records inserted")

# Verify
count = spark.sql("SELECT COUNT(*) as cnt FROM workspace.oil_gas_ops.well_production").collect()[0]['cnt']
print(f"Total records in table: {count}")

# ---------------------------------------------------------------------------
# Cell 4: Set Up Reverse ETL Sync (Triggered Mode)
# ---------------------------------------------------------------------------
from databricks.sdk.service.postgres import (
    SyncedTable,
    SyncedTableSyncedTableSpec,
    SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy,
)

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
result = op.wait()
print(f"Sync table created: {result.name}")
print(f"State: {result.status.detailed_state}")
print(f"Pipeline ID: {result.status.pipeline_id}")

# ---------------------------------------------------------------------------
# Cell 5: Verify Sync Status
# ---------------------------------------------------------------------------
import time

for i in range(10):
    st = w.postgres.get_synced_table(name="synced_tables/workspace.oil_gas_ops.synced_well_production")
    state = st.status.detailed_state
    print(f"Attempt {i+1}: State = {state}")
    if 'SYNCED' in str(state) and 'PROVISIONING' not in str(state):
        break
    time.sleep(15)

if st.status.ongoing_sync_progress:
    p = st.status.ongoing_sync_progress
    print(f"  Synced rows: {p.synced_row_count}")
    print(f"  Total rows: {p.total_row_count}")
print(f"  Message: {st.status.message}")
print("\n✅ Setup complete! You can now deploy the Streamlit app.")