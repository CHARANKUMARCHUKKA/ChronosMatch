# ChronosMatch ⚡

[![ChronosMatch CI](https://github.com/CHARANKUMARCHUKKA/ChronosMatch/actions/workflows/ci.yml/badge.svg)](https://github.com/CHARANKUMARCHUKKA/ChronosMatch/actions)
![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11-blue)
![Cython](https://img.shields.io/badge/compiled-Cython%20C--Extension-brightgreen)
![IPC](https://img.shields.io/badge/IPC-Zero--Copy%20MMap-orange)

**ChronosMatch** is an ultra-low-latency Zero-Copy High-Frequency Trading (HFT) Engine built in Python and Cython.

In High-Frequency Trading, microseconds equal millions of dollars. Python is notoriously dismissed for HFT because its Garbage Collector (GC) causes unpredictable latency spikes, and passing data between multi-processing boundaries usually requires slow serialization (like JSON or Pickle).

ChronosMatch solves this by using a **Cython Limit Order Book (LOB)** built on pure C-structs/pointers, communicating across parallel processes via a **Zero-Copy IPC Bus** utilizing memory-mapped (`mmap`) ring buffers. This architecture achieves sub-microsecond execution latencies without triggering Python garbage collection pauses on the critical path.

---

## 🏗️ Architecture & Key Modules

* **Cython Matching Engine (`chronosmatch/engine/`)**: Compiled C-extension featuring $O(1)$ best bid/ask lookups, $O(\log K)$ binary search price levels, strict FIFO price-time priority, order cancellation support, and an $O(1)$ free-list memory pool eliminating memory leaks.
* **Zero-Copy IPC Bus (`chronosmatch/ipc/`)**: Custom circular ring buffer mapped directly to system memory (Windows Named Shared Memory) with cache-aligned (32-byte / 48-byte) C structures.
* **Market Simulator & Feeds (`chronosmatch/simulator/`)**:
  - `market_sim.py`: High-throughput asynchronous synthetic generator simulating micro-structure Brownian motion and order cancellations (up to 600k+ ops/sec).
  - `binance_feed.py`: Live asynchronous WebSocket consumer streaming real-time BTC/USDT trades from Binance.
* **Latency Monitor (`chronosmatch/monitor/`)**: Real-time terminal HUD built with `curses` displaying Min, Max, Avg, P50, P95, and P99 microsecond execution latencies and live order tape.
* **Web Dashboard (`web_dashboard.py`)**: Institutional quantitative research UI powered by Streamlit and Plotly with 3D order flow, Bollinger Bands, RSI, MACD, and real-time execution tape.

---

## ⚙️ Prerequisites & Installation

1. **Prerequisites:**
   - **Windows:** [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (Desktop development with C++).
   - **Linux:** `build-essential` or `gcc`.
   - **Python:** 3.8+ (64-bit recommended).

2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Compile the Cython Engine:**
   ```bash
   python setup.py build_ext --inplace
   ```

---

## 🏃‍♂️ Usage

### 1. Launch the Main Orchestrator
Start the multi-process engine with the synthetic market feed:
```bash
python main.py --feed sim
```

To stream live BTC/USDT trades from Binance:
```bash
python main.py --feed binance
```

To run headlessly without the terminal curses HUD:
```bash
python main.py --feed sim --no-monitor --duration 60
```

### 2. Run the Benchmark Suite
Measure actual Cython matching engine throughput and roundtrip microsecond latency:
```bash
python benchmark_suite.py
```

### 3. Run the Multi-Worker Stress Test
Validate lock-free ring buffer concurrency under high memory pressure:
```bash
python stress_test.py
```

### 4. Run the Unit & Integration Tests
Execute the comprehensive test suite:
```bash
python -m unittest discover -s tests
```

### 5. Launch the Web Dashboard
```bash
streamlit run web_dashboard.py
```

### 6. One-Click Windows Launcher
Double-click `start_chronos.bat` or run:
```cmd
start_chronos.bat
```
Automatically compiles Cython in-place, spawns the backend engine & Binance WebSocket feed, and launches the Streamlit quant dashboard in your browser.

### 7. Docker Deployment
Run containerized matching engine and web UI:
```bash
docker-compose up --build
```

---

## 🔬 Benchmark Performance

On modern x86_64 hardware:
- **Ingest Throughput:** ~600,000+ orders/second
- **Execution Matching Latency:** ~0.30 µs minimum, sub-50 µs typical P99 under load
- **Memory Footprint:** Zero allocations on the matching hot path via reusable free-list memory pools

<!-- CI Badge Spec -->
<!-- Shields Metadata -->
<!-- Launcher Guide -->
<!-- Docker Compose Guide -->
