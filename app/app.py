"""
Oil & Gas Well Production Dashboard
=====================================
A Streamlit application for reading and writing Oil & Gas well production data
stored in Databricks Lakebase Postgres.

This app demonstrates:
  - Reading data from Postgres (via psycopg3)
  - Writing data to Postgres (INSERT, UPDATE, DELETE)
  - Interactive dashboards with charts and maps
  - CRUD operations on well production records
  - Connection to Lakebase Postgres with OAuth token rotation

Usage:
  - Databricks App:  Deploy using app.yaml (auto-connects to Lakebase)
  - Local/RStudio:   Set environment variables (see below) and run: streamlit run app.py

Environment Variables (for local development):
  LAKEBASE_PG_HOST      - Postgres endpoint host
  LAKEBASE_PG_DB        - Database name (default: databricks_postgres)
  LAKEBASE_PG_USER      - Your Databricks email/username
  LAKEBASE_PG_PASSWORD  - OAuth token or native Postgres password
  LAKEBASE_PG_PORT      - Port (default: 5432)
  
  OR
  
  LAKEBASE_PG_URL       - Full connection URL (overrides individual vars)
"""

import os
import sys
import json
import time
import logging
from datetime import date, datetime
from decimal import Decimal

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Try importing psycopg3 (preferred) or psycopg2
try:
    import psycopg
    PSYCOPG_VERSION = 3
except ImportError:
    try:
        import psycopg2 as psycopg
        PSYCOPG_VERSION = 2
    except ImportError:
        st.error("psycopg is not installed. Run: pip install 'psycopg[binary]' or psycopg2-binary")
        sys.exit(1)

# Try importing Databricks SDK (needed for Streamlit Cloud / token refresh)
try:
    from databricks.sdk import WorkspaceClient
    DATABRICKS_SDK_AVAILABLE = True
except ImportError:
    DATABRICKS_SDK_AVAILABLE = False

# Streamlit Cloud secrets support
# Use st.secrets.get() which returns None for missing keys instead of raising
try:
    _ = st.secrets.get("_test_nonexistent_key")
    STREAMLIT_SECRETS_AVAILABLE = True
except Exception:
    STREAMLIT_SECRETS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "host": os.environ.get("LAKEBASE_PG_HOST", ""),
    "database": os.environ.get("LAKEBASE_PG_DB", "databricks_postgres"),
    "user": os.environ.get("LAKEBASE_PG_USER", ""),
    "password": os.environ.get("LAKEBASE_PG_PASSWORD", ""),
    "port": int(os.environ.get("LAKEBASE_PG_PORT", "5432")),
}

TABLE_NAME = "synced_well_production"
SCHEMA_NAME = "oil_gas_ops"

# ---------------------------------------------------------------------------
# Database Connection
# ---------------------------------------------------------------------------

@st.cache_resource(ttl=2700)  # Cache for 45 minutes (token expires in 1 hour)
def get_connection():
    """Create a connection to Lakebase Postgres."""
    
    # Debug: show connection diagnostics in Streamlit sidebar
    _debug = os.environ.get("STREAMLIT_DEBUG", "")
    if _debug:
        with st.sidebar:
            st.markdown("### 🔍 Connection Diagnostics")
            st.write(f"**DATABRICKS_LAKEBASE_PG_HOST**: {'set' if os.environ.get('DATABRICKS_LAKEBASE_PG_HOST') else 'not set'}")
            st.write(f"**DATABRICKS_HOST (env)**: {'set' if os.environ.get('DATABRICKS_HOST') else 'not set'}")
            st.write(f"**LAKEBASE_PG_HOST (env)**: {'set' if os.environ.get('LAKEBASE_PG_HOST') else 'not set'}")
            try:
                _sh = st.secrets.get("DATABRICKS_HOST")
                _st = st.secrets.get("DATABRICKS_TOKEN")
                st.write(f"**DATABRICKS_HOST (secret)**: {'set' if _sh else 'not set'}")
                st.write(f"**DATABRICKS_TOKEN (secret)**: {'set' if _st else 'not set'}")
            except Exception as e:
                st.write(f"**st.secrets error**: {e}")
            st.write(f"**SDK available**: {DATABRICKS_SDK_AVAILABLE}")
            st.write(f"**_get_streamlit_cloud_config()**: {_get_streamlit_cloud_config()}")
    
    # --- Path 1: Databricks App (auto-injected credentials) ---
    if os.environ.get("DATABRICKS_LAKEBASE_PG_HOST"):
        host = os.environ["DATABRICKS_LAKEBASE_PG_HOST"]
        db = os.environ.get("DATABRICKS_LAKEBASE_PG_DATABASE", "databricks_postgres")
        user = os.environ.get("DATABRICKS_LAKEBASE_PG_USER", "")
        password = os.environ.get("DATABRICKS_LAKEBASE_PG_PASSWORD", "")
        port = int(os.environ.get("DATABRICKS_LAKEBASE_PG_PORT", "5432"))
    
    # --- Path 2: Streamlit Community Cloud (Databricks SDK token refresh) ---
    elif _get_streamlit_cloud_config():
        return _connect_via_databricks_sdk()
    
    # --- Path 3: Local development (environment variables or URL) ---
    else:
        url = os.environ.get("LAKEBASE_PG_URL")
        if url:
            st.session_state["conn_info"] = "Using LAKEBASE_PG_URL"
            conn = psycopg.connect(url)
            return conn
        host = DEFAULT_CONFIG["host"]
        db = DEFAULT_CONFIG["database"]
        user = DEFAULT_CONFIG["user"]
        password = DEFAULT_CONFIG["password"]
        port = DEFAULT_CONFIG["port"]

    if not host or not user:
        st.error("""
        🔧 **Database connection not configured.**
        
        **For Databricks Apps:** The connection is auto-configured via app.yaml.
        
        **For Streamlit Community Cloud:** Set these secrets in your Streamlit app:
        - `DATABRICKS_HOST` - Your Databricks workspace URL
        - `DATABRICKS_TOKEN` - Your Databricks personal access token
        - `LAKEBASE_PG_HOST` - Your Lakebase Postgres endpoint host
        - `LAKEBASE_PG_USER` - Your Databricks email
        
        **For local development:** Set these environment variables:
        ```bash
        export LAKEBASE_PG_HOST=your-endpoint-host
        export LAKEBASE_PG_USER=your-email@company.com
        export LAKEBASE_PG_PASSWORD=your-oauth-token
        export LAKEBASE_PG_DB=databricks_postgres
        ```
        
        Or use a full URL:
        ```bash
        export LAKEBASE_PG_URL="postgresql://user:password@host:5432/db?sslmode=require"
        ```
        """)
        return None

    st.session_state["conn_info"] = f"Connected to {host}/{db}"
    conn = psycopg.connect(
        host=host,
        dbname=db,
        user=user,
        password=password,
        port=port,
        sslmode="require",
        connect_timeout=30,
    )
    return conn


def _get_streamlit_cloud_config():
    """Check if Streamlit Cloud secrets or DATABRICKS_HOST env var are available."""
    # Always try st.secrets first (works on Streamlit Cloud)
    try:
        host = st.secrets.get("DATABRICKS_HOST")
        token = st.secrets.get("DATABRICKS_TOKEN")
        if host and token:
            return True
    except Exception:
        pass
    # Fallback: check environment variables
    if os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN"):
        return True
    return False


def _connect_via_databricks_sdk():
    """Connect to Lakebase Postgres using Databricks SDK for auto token refresh.
    Used by Streamlit Community Cloud where DATABRICKS_HOST and DATABRICKS_TOKEN
    are available but Lakebase credentials are not auto-injected.
    """
    if not DATABRICKS_SDK_AVAILABLE:
        st.error("databricks-sdk is required for Streamlit Cloud. Add it to requirements.txt.")
        return None

    def _get_secret(key, fallback_env=None):
        # Always try st.secrets first (works on Streamlit Cloud)
        try:
            val = st.secrets.get(key)
            if val:
                return val
        except Exception:
            pass
        return os.environ.get(fallback_env or key, "")

    databricks_host = _get_secret("DATABRICKS_HOST")
    databricks_token = _get_secret("DATABRICKS_TOKEN")
    lakebase_host = _get_secret("LAKEBASE_PG_HOST")
    lakebase_user = _get_secret("LAKEBASE_PG_USER")
    lakebase_db = _get_secret("LAKEBASE_PG_DB") or "databricks_postgres"
    lakebase_port = _get_secret("LAKEBASE_PG_PORT") or "5432"
    project_name = _get_secret("LAKEBASE_PROJECT") or "databricks-postgres-streamlit"
    branch_name = _get_secret("LAKEBASE_BRANCH") or "production"
    endpoint_name = f"projects/{project_name}/branches/{branch_name}/endpoints/primary"

    try:
        w = WorkspaceClient(host=databricks_host, token=databricks_token)
        cred = w.postgres.generate_database_credential(endpoint=endpoint_name)

        if not lakebase_host:
            endpoint = w.postgres.get_endpoint(name=endpoint_name)
            if hasattr(endpoint, "host") and endpoint.host:
                lakebase_host = endpoint.host

        if not lakebase_host:
            st.error("Set LAKEBASE_PG_HOST in Streamlit secrets to your endpoint host.")
            return None

        st.session_state["conn_info"] = f"Connected to {lakebase_host}/{lakebase_db} (SDK token)"
        # Retry connection — Lakebase endpoint may be waking from scale-to-zero (5-10 sec cold start)
        last_err = None
        for attempt in range(3):
            try:
                conn = psycopg.connect(
                    host=lakebase_host,
                    dbname=lakebase_db,
                    user=lakebase_user,
                    password=cred.token,
                    port=int(lakebase_port),
                    sslmode="require",
                    connect_timeout=30,
                )
                return conn
            except psycopg.OperationalError as e:
                last_err = e
                if attempt < 2:
                    import time as _time
                    _time.sleep(5 * (attempt + 1))  # 5s, then 10s
        raise last_err
    except Exception as e:
        st.error(f"Databricks SDK connection failed: {str(e)[:200]}")
        return None


def execute_query(conn, query, params=None, fetch=True):
    """Execute a SQL query and optionally fetch results."""
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch:
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            cur.close()
            return columns, rows
        conn.commit()
        cur.close()
        return None, None
    except Exception as e:
        # Only rollback if the connection is still open (not dead)
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if not getattr(conn, 'closed', False):
            try:
                conn.rollback()
            except Exception:
                pass
        raise Exception(f"Database error: {str(e)}")


def fetch_dataframe(conn, query, params=None):
    """Execute a query and return results as a pandas DataFrame."""
    columns, rows = execute_query(conn, query, params)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=columns)
    # Convert Decimal to float for display
    for col in df.select_dtypes(include=['object']).columns:
        try:
            df[col] = df[col].astype(float)
        except (ValueError, TypeError):
            pass
    return df

# ---------------------------------------------------------------------------
# Data Operations (CRUD)
# ---------------------------------------------------------------------------

def get_all_wells(conn):
    """Fetch all well production records."""
    return fetch_dataframe(conn, f"""
        SELECT well_id, well_name, operator, field_name, basin, state, county,
               api_number, oil_rate, gas_rate, water_rate, gas_lift_rate,
               water_cut, well_status, production_date, latitude, longitude,
               created_at, updated_at
        FROM {SCHEMA_NAME}.{TABLE_NAME}
        ORDER BY well_id
    """)


def get_well_by_id(conn, well_id):
    """Fetch a single well by ID."""
    columns, rows = execute_query(conn, f"""
        SELECT * FROM {SCHEMA_NAME}.{TABLE_NAME} WHERE well_id = %s
    """, (well_id,))
    if rows:
        return dict(zip(columns, rows[0]))
    return None


def insert_well(conn, data):
    """Insert a new well production record."""
    execute_query(conn, f"""
        INSERT INTO {SCHEMA_NAME}.{TABLE_NAME} (
            well_id, well_name, operator, field_name, basin, state, county,
            api_number, oil_rate, gas_rate, water_rate, gas_lift_rate,
            water_cut, well_status, production_date, latitude, longitude,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['well_id'], data['well_name'], data['operator'], data['field_name'],
        data['basin'], data['state'], data['county'], data.get('api_number'),
        data.get('oil_rate', 0), data.get('gas_rate', 0), data.get('water_rate', 0),
        data.get('gas_lift_rate', 0), data.get('water_cut', 0),
        data['well_status'], data['production_date'],
        data.get('latitude'), data.get('longitude'),
        datetime.now(), datetime.now()
    ), fetch=False)


def update_well_status(conn, well_id, new_status):
    """Update a well's status."""
    execute_query(conn, f"""
        UPDATE {SCHEMA_NAME}.{TABLE_NAME}
        SET well_status = %s, updated_at = %s
        WHERE well_id = %s
    """, (new_status, datetime.now(), well_id), fetch=False)


def update_well_rates(conn, well_id, oil_rate, gas_rate, water_rate, gas_lift_rate, water_cut):
    """Update a well's production rates."""
    execute_query(conn, f"""
        UPDATE {SCHEMA_NAME}.{TABLE_NAME}
        SET oil_rate = %s, gas_rate = %s, water_rate = %s,
            gas_lift_rate = %s, water_cut = %s, updated_at = %s
        WHERE well_id = %s
    """, (oil_rate, gas_rate, water_rate, gas_lift_rate, water_cut, datetime.now(), well_id), fetch=False)


def delete_well(conn, well_id):
    """Delete a well production record."""
    execute_query(conn, f"""
        DELETE FROM {SCHEMA_NAME}.{TABLE_NAME} WHERE well_id = %s
    """, (well_id,), fetch=False)

# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="🛢️ Oil & Gas Well Production",
        page_icon="🛢️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("🛢️ Oil & Gas Well Production Dashboard")
    st.markdown("""
    Interactive dashboard for monitoring and managing well production data.
    Data is synced from **Unity Catalog** → **Lakebase Postgres** via Reverse ETL.
    """)

    # Connection (with retry for endpoint wake-up)
    conn = None
    for _attempt in range(2):
        conn = get_connection()
        if conn is None:
            st.stop()
        # Health check: verify the connection is alive
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            break
        except Exception:
            # Connection is stale (endpoint scaled to zero) — clear cache and retry
            get_connection.clear()
            conn = None
            if _attempt == 0:
                import time as _time
                _time.sleep(3)  # Allow endpoint to wake up
            else:
                st.error("Could not connect to Lakebase Postgres after retry. The endpoint may be waking up — please refresh the page in a few seconds.")
                st.stop()

    if "conn_info" in st.session_state:
        st.sidebar.success(f"✅ {st.session_state['conn_info']}")

    # Sidebar navigation
    st.sidebar.title("📐 Navigation")
    page = st.sidebar.radio("Go to", [
        "📊 Dashboard",
        "📋 Well List",
        "➕ Add New Well",
        "✏️ Edit Well",
        "🗑️ Delete Well",
        "📈 Analytics",
    ])

    # -----------------------------------------------------------------------
    # Page: Dashboard
    # -----------------------------------------------------------------------
    if page == "📊 Dashboard":
        st.header("📊 Production Dashboard")

        df = get_all_wells(conn)
        if df.empty:
            st.warning("No data found. Make sure the Reverse ETL sync has completed.")
            st.stop()

        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Wells", len(df))
        with col2:
            st.metric("Active Wells", len(df[df['well_status'] == 'ACTIVE']))
        with col3:
            st.metric("Total Oil (bbl/day)", f"{df['oil_rate'].sum():,.2f}")
        with col4:
            st.metric("Total Gas (Mcf/day)", f"{df['gas_rate'].sum():,.2f}")

        st.divider()

        # Charts
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Oil Production by Basin")
            basin_oil = df.groupby('basin')['oil_rate'].sum().reset_index()
            basin_oil = basin_oil.sort_values('oil_rate', ascending=False)
            fig = px.bar(basin_oil, x='basin', y='oil_rate', color='basin',
                         labels={'oil_rate': 'Oil Rate (bbl/day)', 'basin': 'Basin'})
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.subheader("Gas Production by Basin")
            basin_gas = df.groupby('basin')['gas_rate'].sum().reset_index()
            basin_gas = basin_gas.sort_values('gas_rate', ascending=False)
            fig = px.bar(basin_gas, x='basin', y='gas_rate', color='basin',
                         labels={'gas_rate': 'Gas Rate (Mcf/day)', 'basin': 'Basin'})
            st.plotly_chart(fig, use_container_width=True)

        # Well Status Distribution
        st.subheader("Well Status Distribution")
        status_counts = df['well_status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        fig = px.pie(status_counts, values='Count', names='Status', title='Well Status Breakdown')
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Page: Well List
    # -----------------------------------------------------------------------
    elif page == "📋 Well List":
        st.header("📋 All Wells")

        df = get_all_wells(conn)
        if df.empty:
            st.warning("No data found.")
            st.stop()

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            basin_filter = st.selectbox("Filter by Basin", ["All"] + sorted(df['basin'].unique().tolist()))
        with col2:
            operator_filter = st.selectbox("Filter by Operator", ["All"] + sorted(df['operator'].unique().tolist()))
        with col3:
            status_filter = st.selectbox("Filter by Status", ["All"] + sorted(df['well_status'].unique().tolist()))

        filtered_df = df.copy()
        if basin_filter != "All":
            filtered_df = filtered_df[filtered_df['basin'] == basin_filter]
        if operator_filter != "All":
            filtered_df = filtered_df[filtered_df['operator'] == operator_filter]
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df['well_status'] == status_filter]

        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(filtered_df)} of {len(df)} wells")

    # -----------------------------------------------------------------------
    # Page: Add New Well
    # -----------------------------------------------------------------------
    elif page == "➕ Add New Well":
        st.header("➕ Add New Well")
        st.markdown("Fill in the details below to add a new well production record.")

        with st.form("add_well_form"):
            col1, col2 = st.columns(2)
            with col1:
                well_id = st.number_input("Well ID *", min_value=1, step=1, value=26)
                well_name = st.text_input("Well Name *", placeholder="e.g., Permian Alpha #30")
                operator = st.text_input("Operator *", placeholder="e.g., Pioneer Natural Resources")
                field_name = st.text_input("Field Name *", placeholder="e.g., Spraberry Trend")
                basin = st.selectbox("Basin *", ["Permian", "Eagle Ford", "Bakken", "Haynesville",
                                                   "Marcellus", "Niobrara", "Anadarko", "Gulf of Mexico"])
                state = st.text_input("State *", placeholder="e.g., Texas")
                county = st.text_input("County *", placeholder="e.g., Midland")
                api_number = st.text_input("API Number", placeholder="e.g., 42-329-10030")

            with col2:
                oil_rate = st.number_input("Oil Rate (bbl/day)", min_value=0.0, value=0.0, step=10.0)
                gas_rate = st.number_input("Gas Rate (Mcf/day)", min_value=0.0, value=0.0, step=10.0)
                water_rate = st.number_input("Water Rate (bbl/day)", min_value=0.0, value=0.0, step=10.0)
                gas_lift_rate = st.number_input("Gas Lift Rate (Mcf/day)", min_value=0.0, value=0.0, step=10.0)
                water_cut = st.number_input("Water Cut (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                well_status = st.selectbox("Well Status *", ["ACTIVE", "SHUT_IN", "MAINTENANCE", "COMPLETED"])
                production_date = st.date_input("Production Date *", value=date.today())
                latitude = st.number_input("Latitude", value=0.0, format="%.6f")
                longitude = st.number_input("Longitude", value=0.0, format="%.6f")

            submitted = st.form_submit_button("➕ Add Well")

            if submitted:
                if not well_name or not operator:
                    st.error("Well Name and Operator are required!")
                else:
                    try:
                        data = {
                            'well_id': int(well_id), 'well_name': well_name, 'operator': operator,
                            'field_name': field_name, 'basin': basin, 'state': state,
                            'county': county, 'api_number': api_number,
                            'oil_rate': float(oil_rate), 'gas_rate': float(gas_rate),
                            'water_rate': float(water_rate), 'gas_lift_rate': float(gas_lift_rate),
                            'water_cut': float(water_cut), 'well_status': well_status,
                            'production_date': production_date, 'latitude': float(latitude),
                            'longitude': float(longitude),
                        }
                        insert_well(conn, data)
                        st.success(f"✅ Well '{well_name}' added successfully!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"❌ Error adding well: {e}")

    # -----------------------------------------------------------------------
    # Page: Edit Well
    # -----------------------------------------------------------------------
    elif page == "✏️ Edit Well":
        st.header("✏️ Edit Well")

        df = get_all_wells(conn)
        if df.empty:
            st.warning("No wells found.")
            st.stop()

        well_options = [f"{row['well_id']} - {row['well_name']}" for _, row in df.iterrows()]
        selected = st.selectbox("Select Well to Edit", well_options)
        selected_well_id = int(selected.split(" - ")[0])

        well = get_well_by_id(conn, selected_well_id)
        if not well:
            st.error("Well not found!")
            st.stop()

        st.subheader(f"Editing: {well['well_name']}")

        tab1, tab2 = st.tabs(["📋 Status", "📈 Production Rates"])

        with tab1:
            with st.form("edit_status_form"):
                current_status = well['well_status']
                new_status = st.selectbox("Well Status", ["ACTIVE", "SHUT_IN", "MAINTENANCE", "COMPLETED"],
                                          index=["ACTIVE", "SHUT_IN", "MAINTENANCE", "COMPLETED"].index(current_status))
                submitted = st.form_submit_button("Update Status")
                if submitted:
                    try:
                        update_well_status(conn, selected_well_id, new_status)
                        st.success(f"✅ Status updated to '{new_status}'")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

        with tab2:
            with st.form("edit_rates_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    oil = st.number_input("Oil Rate (bbl/day)", value=float(well['oil_rate'] or 0), step=10.0)
                    gas = st.number_input("Gas Rate (Mcf/day)", value=float(well['gas_rate'] or 0), step=10.0)
                with col2:
                    water = st.number_input("Water Rate (bbl/day)", value=float(well['water_rate'] or 0), step=10.0)
                    gas_lift = st.number_input("Gas Lift Rate (Mcf/day)", value=float(well['gas_lift_rate'] or 0), step=10.0)
                with col3:
                    wcut = st.number_input("Water Cut (%)", value=float(well['water_cut'] or 0), min_value=0.0, max_value=100.0, step=1.0)

                submitted = st.form_submit_button("Update Rates")
                if submitted:
                    try:
                        update_well_rates(conn, selected_well_id, oil, gas, water, gas_lift, wcut)
                        st.success("✅ Production rates updated!")
                    except Exception as e:
                        st.error(f"❌ Error: {e}")

    # -----------------------------------------------------------------------
    # Page: Delete Well
    # -----------------------------------------------------------------------
    elif page == "🗑️ Delete Well":
        st.header("🗑️ Delete Well")
        st.warning("⚠️ This action cannot be undone. The well record will be permanently removed from Postgres.")

        df = get_all_wells(conn)
        if df.empty:
            st.warning("No wells found.")
            st.stop()

        well_options = [f"{row['well_id']} - {row['well_name']} ({row['basin']})" for _, row in df.iterrows()]
        selected = st.selectbox("Select Well to Delete", well_options)
        selected_well_id = int(selected.split(" - ")[0])

        confirm = st.checkbox("I understand this action is permanent")
        if st.button("🗑️ Delete Well", type="primary", disabled=not confirm):
            try:
                delete_well(conn, selected_well_id)
                st.success(f"✅ Well {selected_well_id} deleted successfully!")
            except Exception as e:
                st.error(f"❌ Error: {e}")

    # -----------------------------------------------------------------------
    # Page: Analytics
    # -----------------------------------------------------------------------
    elif page == "📈 Analytics":
        st.header("📈 Production Analytics")

        df = get_all_wells(conn)
        if df.empty:
            st.warning("No data found.")
            st.stop()

        # Summary by Operator
        st.subheader("Production by Operator")
        operator_summary = df.groupby('operator').agg({
            'oil_rate': 'sum',
            'gas_rate': 'sum',
            'water_rate': 'sum',
            'well_id': 'count'
        }).rename(columns={'well_id': 'well_count'}).reset_index()
        operator_summary = operator_summary.sort_values('oil_rate', ascending=False)
        st.dataframe(operator_summary, use_container_width=True, hide_index=True)

        # Water Cut Distribution
        st.subheader("Water Cut Distribution by Basin")
        fig = px.box(df, x='basin', y='water_cut', color='basin',
                     labels={'water_cut': 'Water Cut (%)', 'basin': 'Basin'})
        st.plotly_chart(fig, use_container_width=True)

        # Oil vs Gas Scatter
        st.subheader("Oil vs Gas Production (by Well)")
        active_df = df[df['well_status'] == 'ACTIVE']
        fig = px.scatter(active_df, x='oil_rate', y='gas_rate', color='basin',
                         hover_name='well_name', size='water_cut',
                         labels={'oil_rate': 'Oil Rate (bbl/day)', 'gas_rate': 'Gas Rate (Mcf/day)'})
        st.plotly_chart(fig, use_container_width=True)

        # Well Map (if coordinates available)
        if 'latitude' in df.columns and 'longitude' in df.columns:
            map_df = df[(df['latitude'].notna()) & (df['longitude'].notna()) &
                       (df['latitude'] != 0) & (df['longitude'] != 0)]
            if not map_df.empty:
                st.subheader("🗺️ Well Locations Map")
                fig = px.scatter_mapbox(map_df, lat='latitude', lon='longitude',
                                       hover_name='well_name', hover_data=['operator', 'basin', 'oil_rate'],
                                       color='well_status', size='oil_rate',
                                       zoom=3, mapbox_style='open-street-map')
                st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
