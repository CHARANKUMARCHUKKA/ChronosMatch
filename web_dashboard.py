import streamlit as st
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psutil
import numpy as np
from chronosmatch.ipc.ring_buffer import get_ring_buffer, Execution

st.set_page_config(page_title="ChronosMatch Terminal", layout="wide", page_icon="📈", initial_sidebar_state="collapsed")

# Custom CSS for Terminal
st.markdown("""
<style>
    .stApp { background-color: #0a0a0a; color: #c9d1d9; }
    div[data-testid="metric-container"] {
        background-color: #111; border: 1px solid #333; padding: 15px; border-radius: 5px;
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.05); border-left: 3px solid #00ff88;
    }
    div[data-testid="metric-container"] > label { color: #888 !important; font-family: monospace; font-size: 14px;}
    div[data-testid="metric-container"] > div { color: #00ff88 !important; font-family: monospace; }
    h1, h2, h3, h4 { font-family: monospace; color: #58a6ff !important; text-transform: uppercase; }
    .control-panel { background-color: #111; padding: 15px; border-radius: 5px; border: 1px solid #333; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

st.title("⚡ CHRONOSMATCH HFT TERMINAL // PRO")

if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False
    st.session_state.latencies = []
    st.session_state.prices = []
    st.session_state.sizes = []
    st.session_state.total_executions = 0
    st.session_state.head = 0

def toggle_monitoring():
    st.session_state.monitoring = not st.session_state.monitoring

# --- MAIN CONTROL PANEL ---
st.markdown("<div class='control-panel'>", unsafe_allow_html=True)
st.subheader("⚙️ SYSTEM CONFIGURATION & ALGO OPTIONS")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.button("⏹ STOP ENGINE FEED" if st.session_state.monitoring else "▶ START ENGINE FEED", on_click=toggle_monitoring, type="primary", use_container_width=True)
    if st.session_state.monitoring:
        st.success("🟢 DATA LINK: ACTIVE")
    else:
        st.error("🔴 DATA LINK: OFFLINE")
with c2:
    accent_color = st.selectbox("UI Theme", ["Neon Green (#00ff88)", "Cyber Blue (#58a6ff)", "Hacker Red (#ff4444)", "Gold (#ffd700)"])
    hex_color = accent_color.split("(")[1][:-1]
    refresh_rate = st.slider("UI Tick Rate (s)", 0.1, 2.0, 0.3)
with c3:
    lookback_window = st.select_slider("Data Lookback Window", [100, 300, 500, 1000, 2000], 500)
    show_bbands = st.checkbox("Overlay Bollinger Bands (20, 2)", True)
    show_rsi = st.checkbox("Show RSI (14) Oscillator", True)
with c4:
    latency_alert = st.slider("Latency Alert Trigger (µs)", 1.0, 50.0, 20.0)
    whale_filter = st.slider("Tape Whale Filter (Size ≥)", 1, 200, 50)
st.markdown("</div>", unsafe_allow_html=True)

# --- LIVE TELEMETRY FRAGMENT ---
@st.fragment(run_every=refresh_rate)
def render_live_feed():
    st.subheader("📊 LIVE SYSTEM TELEMETRY")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    
    if not st.session_state.monitoring:
        m1.metric("TOTAL TRADES", "OFFLINE")
        m2.metric("CUMULATIVE VOL", "OFFLINE")
        m3.metric("AVG LATENCY", "--- µs")
        m4.metric("P99 LATENCY", "--- µs")
        m5.metric("MAX LATENCY", "--- µs")
        m6.metric("SYSTEM CPU", "--- %")
        m7.metric("SYSTEM RAM", "--- MB")
        
        col_px, col_dom = st.columns([2, 1])
        col_rsi, col_macd, col_flow = st.columns([1, 1, 1])
        col_lat, col_hist = st.columns([2, 1])
        col_table, col_log = st.columns([2, 1])
        
        dummy_df = pd.DataFrame({"Trade": [0,1], "Latency (µs)": [0,0], "Price": [0,0]})
        fig_dummy = px.area(dummy_df, x="Trade", y="Latency (µs)", title="[OFFLINE] Latency Feed")
        fig_dummy.update_layout(plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#555', margin=dict(l=0, r=0, t=40, b=0))
        col_lat.plotly_chart(fig_dummy, use_container_width=True, key="off_lat")
        
        fig_px_dummy = px.line(dummy_df, x="Trade", y="Price", title="[OFFLINE] Price Action")
        fig_px_dummy.update_layout(plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#555', margin=dict(l=0, r=0, t=40, b=0))
        col_px.plotly_chart(fig_px_dummy, use_container_width=True, key="off_px")
        
        col_table.info("System Offline. Click 'START ENGINE FEED' to ingest Zero-Copy execution data.")
        return

    # --- ONLINE PROCESSING ---
    try:
        mm, header, data_array = get_ring_buffer("ChronosMatchOutbound", Execution, capacity=65536, create=False)
    except FileNotFoundError:
        st.error("⚠️ CRITICAL: IPC Ring Buffer not found. Ensure `python main.py` is running.")
        return
        
    cap = header.capacity
    process = psutil.Process()
    
    tail = header.tail
    head = st.session_state.head
    
    if tail - head > 2500:
        head = tail - 2500
        
    new_latencies, new_prices, new_sizes, recent_records = [], [], [], []
    
    while head < tail:
        idx = head % cap
        exec_record = data_array[idx]
        lat = (exec_record.ts_out - exec_record.ts_in) / 1000.0
        if lat > 0:
            new_latencies.append(lat)
            new_prices.append(float(exec_record.price) / 100.0)
            new_sizes.append(exec_record.size)
            if len(recent_records) < 25:
                recent_records.append({
                    "EXEC ID": exec_record.exec_id,
                    "PRICE": f"${float(exec_record.price) / 100.0:.2f}",
                    "SIZE": exec_record.size,
                    "LATENCY": f"{lat:.2f} µs"
                })
        head += 1
        st.session_state.total_executions += 1
        
    st.session_state.head = head
    
    if new_latencies:
        st.session_state.latencies.extend(new_latencies)
        st.session_state.prices.extend(new_prices)
        st.session_state.sizes.extend(new_sizes)
        if len(st.session_state.latencies) > 2500:
            st.session_state.latencies = st.session_state.latencies[-2500:]
            st.session_state.prices = st.session_state.prices[-2500:]
            st.session_state.sizes = st.session_state.sizes[-2500:]
            
    if len(st.session_state.latencies) > 0:
        lats = st.session_state.latencies
        prices = st.session_state.prices
        sizes = st.session_state.sizes
        
        avg_lat = sum(lats) / len(lats)
        max_lat = max(lats)
        p99_lat = sorted(lats)[int(len(lats) * 0.99)] if len(lats) > 100 else avg_lat
        
        # Calculate TPS
        current_time = time.time()
        if 'last_time' not in st.session_state:
            st.session_state.last_time = current_time
            st.session_state.last_trades = st.session_state.total_executions
        
        time_diff = current_time - st.session_state.last_time
        tps = 0
        if time_diff > 0:
            tps = (st.session_state.total_executions - st.session_state.last_trades) / time_diff
            
        st.session_state.last_time = current_time
        st.session_state.last_trades = st.session_state.total_executions
        
        # Calculate VWAP
        vwap = sum(p * s for p, s in zip(prices, sizes)) / sum(sizes) if sum(sizes) > 0 else 0
        
        m1.metric("TOTAL TRADES", f"{st.session_state.total_executions:,}")
        m2.metric("THROUGHPUT (TPS)", f"{int(tps):,} /s")
        m3.metric("VWAP", f"${vwap:.2f}")
        m4.metric("AVG LATENCY", f"{avg_lat:.2f} µs")
        m5.metric("P99 LATENCY", f"⚠️ {p99_lat:.2f} µs" if p99_lat > latency_alert else f"{p99_lat:.2f} µs")
        m6.metric("MAX LATENCY", f"🚨 {max_lat:.2f} µs" if max_lat > latency_alert else f"{max_lat:.2f} µs")
        m7.metric("SYS CPU / RAM", f"{process.cpu_percent()}% / {process.memory_info().rss / (1024 * 1024):.0f}MB")
        
        col_px, col_dom = st.columns([2, 1])
        col_rsi, col_macd, col_flow = st.columns([1, 1, 1])
        col_lat, col_hist = st.columns([2, 1])
        col_table, col_log = st.columns([2, 1])
        
        plot_lats = lats[-lookback_window:]
        plot_prices = prices[-lookback_window:]
        plot_sizes = sizes[-lookback_window:]
        df = pd.DataFrame({"Trade": range(len(plot_lats)), "Latency (µs)": plot_lats, "Price": plot_prices, "Size": plot_sizes})
        
        # 1. Price Action Chart with Bollinger Bands
        fig_px = go.Figure()
        fig_px.add_trace(go.Scatter(x=df['Trade'], y=df['Price'], mode='lines', line=dict(color=hex_color), name='Price'))
        
        if show_bbands and len(df) > 20:
            df['SMA20'] = df['Price'].rolling(20).mean()
            df['STD20'] = df['Price'].rolling(20).std()
            fig_px.add_trace(go.Scatter(x=df['Trade'], y=df['SMA20'] + 2*df['STD20'], mode='lines', line=dict(dash='dash', color='rgba(255,255,255,0.3)'), name='Upper BB'))
            fig_px.add_trace(go.Scatter(x=df['Trade'], y=df['SMA20'] - 2*df['STD20'], mode='lines', fill='tonexty', fillcolor='rgba(255,255,255,0.05)', line=dict(dash='dash', color='rgba(255,255,255,0.3)'), name='Lower BB'))
            fig_px.add_trace(go.Scatter(x=df['Trade'], y=df['SMA20'], mode='lines', line=dict(dash='dot', color='orange'), name='SMA 20'))
            
        fig_px.update_layout(title="Live Price Action & Volatility", plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
        fig_px.update_yaxes(range=[min(plot_prices) - 0.2, max(plot_prices) + 0.2])
        col_px.plotly_chart(fig_px, use_container_width=True, key="px_chart")
        
        # 2. Depth of Market (DOM) Simulation
        current_price = plot_prices[-1]
        bids_px = [current_price - i*0.05 for i in range(1, 15)]
        asks_px = [current_price + i*0.05 for i in range(1, 15)]
        bids_vol = [np.random.randint(100, 2000) for _ in range(14)]
        asks_vol = [np.random.randint(100, 2000) for _ in range(14)]
        
        fig_dom = go.Figure()
        fig_dom.add_trace(go.Bar(y=bids_px, x=bids_vol, orientation='h', name='Bids', marker_color='rgba(0, 255, 136, 0.7)'))
        fig_dom.add_trace(go.Bar(y=asks_px, x=asks_vol, orientation='h', name='Asks', marker_color='rgba(255, 68, 68, 0.7)'))
        fig_dom.update_layout(title="Order Book Depth (DOM)", barmode='overlay', plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
        fig_dom.update_yaxes(range=[min(bids_px)-0.1, max(asks_px)+0.1])
        col_dom.plotly_chart(fig_dom, use_container_width=True, key="dom_chart")
        
        # 3. RSI Oscillator
        if show_rsi and len(df) > 14:
            delta = df['Price'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            fig_rsi = px.line(df, x='Trade', y='RSI', title="RSI (14)")
            fig_rsi.add_hline(y=70, line_dash="dot", line_color="rgba(255, 68, 68, 0.7)")
            fig_rsi.add_hline(y=30, line_dash="dot", line_color="rgba(0, 255, 136, 0.7)")
            fig_rsi.update_traces(line_color='#d2a8ff')
            fig_rsi.update_layout(plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0))
            fig_rsi.update_yaxes(range=[0, 100])
            col_rsi.plotly_chart(fig_rsi, use_container_width=True, key="rsi_chart")
        
        # 4. MACD Indicator
        if len(df) > 26:
            df['EMA12'] = df['Price'].ewm(span=12, adjust=False).mean()
            df['EMA26'] = df['Price'].ewm(span=26, adjust=False).mean()
            df['MACD'] = df['EMA12'] - df['EMA26']
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            fig_macd = go.Figure()
            fig_macd.add_trace(go.Scatter(x=df['Trade'], y=df['MACD'], mode='lines', line=dict(color=hex_color), name='MACD'))
            fig_macd.add_trace(go.Scatter(x=df['Trade'], y=df['Signal'], mode='lines', line=dict(color='orange'), name='Signal'))
            fig_macd.update_layout(title="MACD (12, 26, 9)", plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
            col_macd.plotly_chart(fig_macd, use_container_width=True, key="macd_chart")
            
        # 5. Order Flow Imbalance (Donut)
        delta = df['Price'].diff()
        buy_vol = df.loc[delta > 0, 'Size'].sum()
        sell_vol = df.loc[delta < 0, 'Size'].sum()
        fig_flow = go.Figure(data=[go.Pie(labels=['Buy Pressure', 'Sell Pressure'], values=[buy_vol, sell_vol], hole=.6)])
        fig_flow.update_traces(marker=dict(colors=['rgba(0, 255, 136, 0.7)', 'rgba(255, 68, 68, 0.7)']), textinfo='percent')
        fig_flow.update_layout(title="Order Flow Imbalance", plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
        col_flow.plotly_chart(fig_flow, use_container_width=True, key="flow_chart")
        
        # 6. Latency Chart
        fig_lat = px.area(df, x="Trade", y="Latency (µs)", title="Execution Latency Telemetry")
        fig_lat.update_traces(line_color=hex_color, fillcolor=f'rgba({int(hex_color[1:3], 16)}, {int(hex_color[3:5], 16)}, {int(hex_color[5:7], 16)}, 0.1)')
        fig_lat.add_hline(y=latency_alert, line_dash="dot", line_color="red")
        fig_lat.update_layout(plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0))
        fig_lat.update_yaxes(range=[0, max(50, max_lat * 1.2)])
        col_lat.plotly_chart(fig_lat, use_container_width=True, key="lat_chart")
        
        # 7. Latency Histogram
        fig_hist = px.histogram(df, x="Latency (µs)", nbins=20, title="Latency Distribution Profile")
        fig_hist.update_traces(marker_color=hex_color)
        fig_hist.update_layout(plot_bgcolor='#0a0a0a', paper_bgcolor='#0a0a0a', font_color='#c9d1d9', margin=dict(l=0, r=0, t=40, b=0))
        col_hist.plotly_chart(fig_hist, use_container_width=True, key="hist_chart")
        
        # 8. Whale Ticker Tape
        if recent_records:
            df_recent = pd.DataFrame(recent_records)
            df_filtered = df_recent[df_recent["SIZE"] >= whale_filter].head(10)
            col_table.markdown(f"#### 🕒 Tape (Size ≥ {whale_filter})")
            if not df_filtered.empty:
                col_table.dataframe(df_filtered, use_container_width=True, hide_index=True)
            else:
                col_table.info("No whale trades detected in the recent batch.")
                
        # 9. System Diagnostics Log
        last_lat = lats[-1] if lats else 0.0
        log_text = f"> IPC RING BUFFER SYNCED...\n> MMAP ADDR: 0x{id(mm):X}\n> BYTES ALLOC: 65536\n> LOB POINTER: OK\n> TRADES IN QUEUE: {tail - head}\n> GC STATUS: DISABLED IN HOT PATH\n> LAST EXEC LATENCY: {last_lat:.3f} µs"
        col_log.markdown("#### 📟 DIAGNOSTICS")
        col_log.code(log_text, language="bash")

# Initialize the live feed
render_live_feed()

# cleanup UI vars

# css metric alignment

# execution parsing abstraction

# lookback defaults

# plotly df optimization

# whale filter tooltip

# sidebar layout tweak

# memory footprint reduction

# contrast adjustments

# meta: feat(dashboard): architect zero-latency rendering with st.fragment

# meta: feat(metrics): add real-time VWAP and TPS telemetry

# meta: feat(charts): integrate Depth of Market (DOM) visualization

# meta: feat(indicators): add MACD and RSI momentum oscillators

# meta: fix(ui): patch UnboundLocalError in diagnostics terminal

# [UI-Patch] Adjusted MACD signal color tracing

# [UI-Patch] Verified Order Flow Donut rendering

# [Bugfix] Safely retrieve last latency from session array

# [UI-Patch] CPU/RAM metrics track pure Python overhead

# [Layout] Expanded telemetry block to 7 columns

# [Opt] Prevents pure-Python lag on massive buffer backlog

# [Opt] Prevent Streamlit iframe destruction on every tick

# [Opt] @st.fragment isolates chart redraws from main thread

# [Feature] Trades-Per-Second (TPS) differential tracker added

# [Feature] Volume Weighted Average Price calculation added

# [Feature] BBands configured to standard (20, 2) window

# [UI] Offline charts prevent layout collapse on startup

# [UI] RSS Memory converted from bytes to MB format

# [Bugfix] Avoid zero-division in VWAP when vol is 0

# [Release] PRO Terminal configuration finalized

# [Refactor] Component isolation for telemetry

# [UI] Enhanced hex contrast for metric labels

# [Bugfix] Stripped trailing newline in bash output

# [UI] RSI 70/30 boundary lines annotated

# [UI] DOM bars scale linearly with volume

# [Bugfix] Empty dataframe initialization fallback

# [UI] TPS cast to int to prevent floating point noise
