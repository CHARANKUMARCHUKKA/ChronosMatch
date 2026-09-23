# ChronosMatch ⚡

**ChronosMatch** is a prototype Zero-Copy High-Frequency Trading (HFT) Engine built in Python and Cython. 

In High-Frequency Trading, microseconds equal millions of dollars. Python is notoriously dismissed for HFT because its Garbage Collector (GC) causes unpredictable latency spikes, and passing data between multi-processing boundaries usually requires slow serialization (like JSON or Pickle).

ChronosMatch solves this by using a **Cython Limit Order Book (LOB)** built on pure C-structs/pointers and communicating across parallel processes via a **Zero-Copy IPC Bus** utilizing memory-mapped (`mmap`) ring buffers. This architecture achieves sub-50 microsecond execution latencies without triggering a single Python garbage collection pause on the critical path.

---

## 🏗️ Architecture & Key Modules

* **Cython Matching Engine (`chronosmatch/engine/`)**: The core Limit Order Book algorithm compiled to a C-extension. It reads and writes directly to RAM addresses using C-pointers, completely bypassing Python objects during trade matching.
* **Zero-Copy IPC Bus (`chronosmatch/ipc/`)**: A custom ring buffer mapped directly to system memory (Windows Named Shared Memory). It allows the Python and Cython processes to share data instantly without serialization overhead.
* **Market Simulator (`chronosmatch/simulator/`)**: A high-throughput `asyncio` loop simulating a massive wave of Nasdaq/NYSE financial tick data, inserting it directly into the `mmap` inbound buffer.
* **Latency Monitor (`chronosmatch/monitor/`)**: A live terminal dashboard built with `curses` that visualizes real-time execution speeds (Min, Max, Avg, P99) in microseconds (µs).

---

## ⚙️ Prerequisites

To run ChronosMatch, you will need a C compiler installed on your system to compile the Cython extension:
* **Windows:** [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (Install the "Desktop development with C++" workload).
* **Linux:** `build-essential` or `gcc`.
* **Python:** 3.8+ (64-bit recommended)

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/CHARANKUMARCHUKKA/ChronosMatch.git
   cd ChronosMatch
   ```

2. **Install requirements:**
   ```bash
   pip install cython setuptools
   ```

3. **Compile the Cython Engine:**
   Build the C-extension in place.
   ```bash
   python setup.py build_ext --inplace
   ```

---

## 🏃‍♂️ Usage

To start the trading system, run the main orchestrator script:

```bash
python main.py
```

This will automatically spawn the multi-process architecture. Your terminal will clear and present the **ChronosMatch Latency Dashboard**. The simulator will begin pumping thousands of orders into the memory buffer, and the C-engine will match them in real-time. 

Use `Ctrl + C` to exit the dashboard.
