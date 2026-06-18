"""
Streamlit dashboard for the weather data pipeline.

Reads from the weather_observations table in PostgreSQL and displays
live metrics, historical charts, and a raw data table.
"""

import os

import pandas as pd
import psycopg2
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Weather Pipeline Dashboard",
    page_icon="🌤️",
    layout="wide",
)


# ── Database connection ─────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "airflow-postgresql"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )


def table_exists(conn) -> bool:
    """Check whether the weather_observations table has been created."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'weather_observations'
            );
        """)
        return cur.fetchone()[0]


@st.cache_data(ttl=15)
def load_data() -> pd.DataFrame:
    conn = get_connection()
    if not table_exists(conn):
        return pd.DataFrame()
    return pd.read_sql(
        "SELECT * FROM weather_observations ORDER BY ingested_at DESC",
        conn,
    )


# ── Header ───────────────────────────────────────────────────────────
st.title("🌤️ Weather Pipeline Dashboard")
st.caption(
    "Live results from the **ingest → transform → load** pipeline running on Airflow / Kubernetes."
)

# ── Load data ────────────────────────────────────────────────────────
df = load_data()

if df.empty:
    st.info(
        "No observations yet. Trigger the DAG to populate data:\n\n"
        "```bash\n"
        "kubectl exec airflow-scheduler-0 -c scheduler -n data-platform -- "
        "airflow dags trigger multicloud_pipeline_local\n"
        "```"
    )
    st.stop()

# ── Key metrics (latest reading) ────────────────────────────────────
latest = df.iloc[0]

st.subheader("Latest Reading")
col1, col2, col3, col4 = st.columns(4)

col1.metric("🌡️ Temperature", f"{latest['temperature_c']:.1f} °C")
col2.metric("💨 Wind Speed", f"{latest['wind_speed_kmh']:.1f} km/h")
col3.metric("💧 Humidity", f"{latest['humidity_pct']:.0f}%")
col4.metric("📍 Location", f"{latest['latitude']:.2f}°N, {latest['longitude']:.2f}°E")

st.divider()

# ── Charts ───────────────────────────────────────────────────────────
st.subheader("Historical Trends")

# Prepare time-series data (ascending order for charts)
ts = df.sort_values("ingested_at").set_index("ingested_at")

tab1, tab2, tab3 = st.tabs(["Temperature", "Wind Speed", "Humidity"])

with tab1:
    st.line_chart(ts["temperature_c"], color="#ff6347")
    st.caption("Temperature in °C over time")

with tab2:
    st.line_chart(ts["wind_speed_kmh"], color="#4682b4")
    st.caption("Wind speed in km/h over time")

with tab3:
    st.line_chart(ts["humidity_pct"], color="#32cd32")
    st.caption("Relative humidity (%) over time")

st.divider()

# ── Summary statistics ───────────────────────────────────────────────
st.subheader("Summary Statistics")

stats_cols = ["temperature_c", "wind_speed_kmh", "humidity_pct"]
stats_df = df[stats_cols].describe().T
stats_df.index = ["Temperature (°C)", "Wind Speed (km/h)", "Humidity (%)"]
st.dataframe(stats_df, use_container_width=True)

st.divider()

# ── Raw data table ───────────────────────────────────────────────────
st.subheader(f"Raw Observations ({len(df)} rows)")
st.dataframe(
    df.drop(columns=["id"], errors="ignore"),
    use_container_width=True,
    hide_index=True,
)

# ── Footer ───────────────────────────────────────────────────────────
st.caption(
    "Auto-refreshes every 15 seconds. "
    "Source: [Open-Meteo API](https://open-meteo.com/) — Paris, France."
)
