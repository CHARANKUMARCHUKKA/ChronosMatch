import streamlit as st
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Execution

st.set_page_config(page_title="ChronosMatch Terminal", layout="wide", page_icon="📈", initial_sidebar_state="expanded")

# Inject Custom CSS for a Bloomberg/Cyberpunk HFT Terminal look
st.markdown("""
<style>
    /* Dark Theme Overrides */
    .stApp {
        background-color: #0e1117;
        color: #c9d1d9;
    }
    
    /* Glowing Metrics */
    div[data-testid="metric-container"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.1);
        border-left: 4px solid #00ff88;
    }
    div[data-testid="metric-container"] > label {
        color: #8b949e !important;
        font-weight: 600;
        font-family: 'Courier New', Courier, monospace;
    }
    div[data-testid="metric-container"] > div {
        color: #00ff88 !important;
        font-family: 'Courier New', Courier, monospace;
        text-shadow: 0 0 5px rgba(0, 255, 136, 0.5);
    }
    
    h1 {
        font-family: 'Courier New', Courier, monospace;
        color: #58a6ff !important;
        text-transform: uppercase;
        border-bottom: 2px solid #30363d;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("⚡ CHRONOSMATCH HFT TERMINAL // LIVE")

if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False
    st.session_state.latencies = []
    st.session_state.prices = []
    st.session_state.sizes = []
    st.session_state.total_executions = 0
    st.session_state.head = 0

def toggle_monitoring():
    st.session_state.monitoring = not st.session_state.monitoring

# Big Start Button on Main Page
col_btn, _ = st.columns([1, 5])
col_btn.button("⏹ STOP FEED" if st.session_state.monitoring else "▶ START FEED", on_click=toggle_monitoring, type="primary", use_container_width=True)

# --- SIDEBAR OPTIONS ---
st.sidebar.header("⚙️ TERMINAL CONTROLS")
st.sidebar.markdown("Customize your telemetry feed:")

lookback_window = st.sidebar.select_slider(
    "Chart Lookback Window (Trades)",
    options=[100, 300, 500, 1000, 2000],
    value=500
)

refresh_rate = st.sidebar.slider(
    "UI Refresh Rate (Seconds)",
    min_value=0.1, max_value=2.0, value=0.3, step=0.1
)

show_hist = st.sidebar.checkbox("Show Latency Histogram", value=True)
show_table = st.sidebar.checkbox("Show Live Ticker Tape", value=True)

st.sidebar.markdown("---")
st.sidebar.header("📈 ADVANCED ANALYTICS")

accent_color = st.sidebar.selectbox("Dashboard Accent Color", options=["Neon Green (#00ff88)", "Cyber Blue (#58a6ff)", "Hacker Red (#ff4444)", "Gold (#ffd700)"])
hex_color = accent_color.split("(")[1][:-1]

show_sma = st.sidebar.checkbox("Overlay 50-Trade Moving Average", value=True)
whale_filter = st.sidebar.slider("Ticker Tape: Min Volume (Whale Filter)", min_value=1, max_value=200, value=1)
latency_alert = st.sidebar.slider("Latency Alert Threshold (µs)", min_value=1.0, max_value=50.0, value=20.0)

st.sidebar.markdown("---")
st.sidebar.markdown("**Engine Status:**")

if st.session_state.monitoring:
    st.sidebar.success("🟢 ONLINE - Receiving Data")
else:
    st.sidebar.error("🔴 OFFLINE - Feed Paused")

try:
    mm, header, data_array = get_ring_buffer("ChronosMatchOutbound", Execution, capacity=65536, create=False)
except FileNotFoundError:
    st.error("⚠️ SYSTEM OFFLINE. Run `python main.py` in your terminal to initialize the Cython engine.")
    st.stop()

# Layout Containers
m1, m2, m3, m4, m5 = st.columns(5)
met_total = m1.empty()
met_vol = m2.empty()
met_avg = m3.empty()
met_p99 = m4.empty()
met_max = m5.empty()

st.markdown("---")
col_chart1, col_chart2 = st.columns(2)
chart_latency = col_chart1.empty()
chart_price = col_chart2.empty()

st.markdown("---")
col_hist, col_table = st.columns([1, 1])
chart_hist = col_hist.empty()
table_recent = col_table.empty()

status_msg = st.empty()

if st.session_state.monitoring:
    cap = header.capacity
    
    while st.session_state.monitoring:
        tail = header.tail
        head = st.session_state.head
        new_latencies = []
        new_prices = []
        new_sizes = []
        recent_records = []
        
        while head < tail:
            idx = head % cap
            exec_record = data_array[idx]
            latency_us = (exec_record.ts_out - exec_record.ts_in) / 1000.0
            
            if latency_us > 0:
                new_latencies.append(latency_us)
                new_prices.append(float(exec_record.price) / 100.0)
                new_sizes.append(exec_record.size)
                
                if len(recent_records) < 30: # Grab more for filtering
                    recent_records.append({
                        "EXEC ID": exec_record.exec_id,
                        "PRICE": f"${float(exec_record.price) / 100.0:.2f}",
                        "SIZE": exec_record.size,
                        "LATENCY (µs)": f"{latency_us:.2f}"
                    })
            
            head += 1
            st.session_state.total_executions += 1
            
        st.session_state.head = head
        
        if new_latencies:
            st.session_state.latencies.extend(new_latencies)
            st.session_state.prices.extend(new_prices)
            st.session_state.sizes.extend(new_sizes)
            
            if len(st.session_state.latencies) > 2000:
                st.session_state.latencies = st.session_state.latencies[-2000:]
                st.session_state.prices = st.session_state.prices[-2000:]
                st.session_state.sizes = st.session_state.sizes[-2000:]
                
        if len(st.session_state.latencies) > 0:
            status_msg.empty()
            lats = st.session_state.latencies
            prices = st.session_state.prices
            
            avg_lat = sum(lats) / len(lats)
            max_lat = max(lats)
            p99_lat = sorted(lats)[int(len(lats) * 0.99)] if len(lats) > 100 else avg_lat
            total_vol = sum(st.session_state.sizes)
            
            met_total.metric("TOTAL TRADES", f"{st.session_state.total_executions:,}")
            met_vol.metric("CUMULATIVE VOL", f"{total_vol:,}")
            met_avg.metric("AVG LATENCY", f"{avg_lat:.2f} µs")
            
            # Alert coloring for metrics
            p99_val = f"⚠️ {p99_lat:.2f} µs" if p99_lat > latency_alert else f"{p99_lat:.2f} µs"
            max_val = f"🚨 {max_lat:.2f} µs" if max_lat > latency_alert else f"{max_lat:.2f} µs"
            
            met_p99.metric("P99 LATENCY", p99_val)
            met_max.metric("MAX LATENCY", max_val)
            
            plot_lats = lats[-lookback_window:]
            plot_prices = prices[-lookback_window:]
            df = pd.DataFrame({"Trade": range(len(plot_lats)), "Latency (µs)": plot_lats, "Price": plot_prices})
            
            # Latency Chart with Alert Line
            fig_lat = px.area(df, x="Trade", y="Latency (µs)", title=f"Latency Feed (Last {lookback_window})")
            fig_lat.update_traces(line_color=hex_color, fillcolor=f'rgba({int(hex_color[1:3], 16)}, {int(hex_color[3:5], 16)}, {int(hex_color[5:7], 16)}, 0.1)')
            fig_lat.add_hline(y=latency_alert, line_dash="dot", line_color="red", annotation_text="Alert Threshold", annotation_position="top right")
            fig_lat.update_layout(plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0))
            fig_lat.update_yaxes(range=[0, max(50, max_lat * 1.2)])
            chart_latency.plotly_chart(fig_lat, use_container_width=True, key=f"lat_{time.time()}")
            
            # Price Action Chart with SMA
            fig_px = px.line(df, x="Trade", y="Price", title=f"Price Action (Last {lookback_window})")
            fig_px.update_traces(line_color=hex_color)
            
            if show_sma and len(df) > 50:
                df['SMA_50'] = df['Price'].rolling(window=50).mean()
                fig_px.add_scatter(x=df['Trade'], y=df['SMA_50'], mode='lines', name='SMA 50', line=dict(color='orange', dash='dot'))
                
            fig_px.update_layout(plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
            min_px, max_px = min(plot_prices), max(plot_prices)
            fig_px.update_yaxes(range=[min_px - 0.1, max_px + 0.1])
            chart_price.plotly_chart(fig_px, use_container_width=True, key=f"px_{time.time()}")
            
            # Histogram
            if show_hist:
                fig_hist = px.histogram(df, x="Latency (µs)", nbins=20, title="Latency Distribution")
                fig_hist.update_traces(marker_color=hex_color)
                fig_hist.add_vline(x=latency_alert, line_dash="dot", line_color="red")
                fig_hist.update_layout(plot_bgcolor='#0e1117', paper_bgcolor='#0e1117', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0))
                chart_hist.plotly_chart(fig_hist, use_container_width=True, key=f"hist_{time.time()}")
            else:
                chart_hist.empty()
            
            # Ticker Tape with Whale Filter
            if show_table and recent_records:
                df_recent = pd.DataFrame(recent_records)
                df_filtered = df_recent[df_recent["SIZE"] >= whale_filter].head(10)
                table_recent.markdown(f"### 🕒 Ticker Tape (Size ≥ {whale_filter})")
                if not df_filtered.empty:
                    table_recent.dataframe(df_filtered, use_container_width=True, hide_index=True)
                else:
                    table_recent.info("No trades matched the Whale Filter in the latest batch.")
            else:
                table_recent.empty()
        else:
            status_msg.info("⏳ Waiting for engine data... Make sure `python main.py` is currently running in your terminal!")
            
        time.sleep(refresh_rate)
        st.rerun()

# cleanup UI vars

# css metric alignment

# execution parsing abstraction

# lookback defaults

# plotly df optimization

# whale filter tooltip

# sidebar layout tweak
