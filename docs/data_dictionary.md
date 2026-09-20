# 📖 Data Dictionary - Oil & Gas Well Production

> Complete field-by-field reference for the `well_production` table.

---

## Table: `workspace.oil_gas_ops.well_production`

**Purpose**: Stores daily production readings from oil and gas wells across major US basins.

**Row grain**: One row = one well's production reading for one date.

---

## Field Descriptions

| # | Column Name | Data Type | Nullable | Description | Example Value |
|---|-------------|-----------|----------|-------------|---------------|
| 1 | `well_id` | BIGINT | NO | Unique numeric identifier for each well. Primary key. | `1` |
| 2 | `well_name` | STRING | NO | Human-readable well name. | `Permian Alpha #1` |
| 3 | `operator` | STRING | NO | Company operating the well. | `Pioneer Natural Resources` |
| 4 | `field_name` | STRING | NO | Name of the oil/gas field where the well is located. | `Spraberry Trend` |
| 5 | `basin` | STRING | NO | Geological basin. One of: Permian, Eagle Ford, Bakken, Haynesville, Marcellus, Niobrara, Anadarko, Gulf of Mexico. | `Permian` |
| 6 | `state` | STRING | NO | US state where the well is located. | `Texas` |
| 7 | `county` | STRING | NO | County within the state. | `Midland` |
| 8 | `api_number` | STRING | YES | API well identification number (standard US format: SS-CCC-WWWWW). | `42-329-10001` |
| 9 | `oil_rate` | DECIMAL(10,2) | YES | Oil production rate in barrels per day (bbl/day). | `850.50` |
| 10 | `gas_rate` | DECIMAL(10,2) | YES | Gas production rate in thousand cubic feet per day (Mcf/day). | `1250.00` |
| 11 | `water_rate` | DECIMAL(10,2) | YES | Water production rate in barrels per day (bbl/day). | `320.00` |
| 12 | `gas_lift_rate` | DECIMAL(10,2) | YES | Gas lift injection rate in Mcf/day. 0 if no gas lift used. | `150.00` |
| 13 | `water_cut` | DECIMAL(5,2) | YES | Water cut percentage (0-100). Percentage of water in total fluid produced. | `27.35` |
| 14 | `well_status` | STRING | NO | Current well status. One of: ACTIVE, SHUT_IN, MAINTENANCE, COMPLETED. | `ACTIVE` |
| 15 | `production_date` | DATE | NO | Date of the production reading. | `2026-09-15` |
| 16 | `latitude` | DECIMAL(10,6) | YES | Well surface latitude in decimal degrees. | `31.845678` |
| 17 | `longitude` | DECIMAL(10,6) | YES | Well surface longitude in decimal degrees. | `-102.078910` |
| 18 | `created_at` | TIMESTAMP | NO | Timestamp when this record was created. | `2026-09-15 06:00:00` |
| 19 | `updated_at` | TIMESTAMP | NO | Timestamp when this record was last updated. | `2026-09-15 06:00:00` |

---

## Field Categories

### 🆔 Identification Fields
- `well_id` - Primary key, unique per well
- `well_name` - Human-readable name
- `api_number` - Standard US API well identifier

### 🏢 Operator & Location Fields
- `operator` - Drilling/production company
- `field_name` - Sub-basin or geological formation name
- `basin` - Major geological basin
- `state` - US state
- `county` - County within the state
- `latitude` / `longitude` - GPS coordinates

### 📊 Production Metrics
- `oil_rate` - Oil output (barrels/day)
- `gas_rate` - Gas output (Mcf/day)
- `water_rate` - Water output (barrels/day)
- `gas_lift_rate` - Artificial lift gas injection (Mcf/day)
- `water_cut` - Water percentage of total fluid

### 📅 Status & Timestamps
- `well_status` - Operational status
- `production_date` - Date of reading
- `created_at` - Record creation time
- `updated_at` - Last modification time

---

## Data Type Mapping (UC \u2192 Postgres)

| Unity Catalog Type | Postgres Type |
|---------------------|---------------|
| BIGINT | BIGINT |
| STRING | TEXT |
| DECIMAL(10,2) | NUMERIC |
| DECIMAL(5,2) | NUMERIC |
| DATE | DATE |
| TIMESTAMP | TIMESTAMP WITH TIME ZONE |

---

## Basins in the Dataset

| Basin | States | Primary Production | Wells in Dataset |
|-------|--------|-------------------|------------------|
| Permian | Texas, New Mexico | Oil + associated gas | 8 |
| Eagle Ford | Texas | Oil + gas | 3 |
| Bakken | North Dakota | Oil + associated gas | 3 |
| Haynesville | Louisiana | Dry gas | 2 |
| Marcellus | Pennsylvania | Dry gas | 2 |
| Niobrara | Colorado | Oil + gas | 2 |
| Anadarko | Oklahoma | Oil + gas | 2 |
| Gulf of Mexico | Louisiana (offshore) | Oil + gas | 2 |

---

## Well Status Values

| Status | Meaning | Visual Indicator |
|--------|---------|-----------------|
| `ACTIVE` | Well is producing | 🟢 Green |
| `SHUT_IN` | Well is temporarily shut down | 🔴 Red |
| `MAINTENANCE` | Well is under maintenance | 🟡 Yellow |
| `COMPLETED` | Well is completed but not yet producing | ⚪ Gray |