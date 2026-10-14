# ChronosMatch Technical Viva & Evaluation Guide

This guide prepares you for technical review questions, viva discussions, and evaluator demonstrations.

---

## 1. Core Architecture & High-Frequency Trading (HFT)

### Q1: What problem does ChronosMatch solve?
**Answer:**
Traditional Python is ill-suited for High-Frequency Trading (HFT) due to two major architectural constraints:
1. **Garbage Collection (GC) Latency:** Python's generational garbage collection introduces unpredictable "stop-the-world" latency spikes (10ms to 100ms), which is catastrophic when trading decisions occur at microsecond timescales.
2. **IPC Serialization Overhead:** Exchanging order messages across processes via standard mechanisms (Unix/TCP sockets, IPC pipes, or JSON/Pickle serialization) incurs excessive CPU copies and memory allocation.

**ChronosMatch** eliminates both bottlenecks by executing order matching inside a compiled **Cython Limit Order Book (LOB)** using pure C-struct pointers and sharing data across processes via a **Zero-Copy Shared Memory (`mmap`) Ring Buffer**.

---

## 2. Zero-Copy Inter-Process Communication (IPC)

### Q2: How does the Zero-Copy IPC Bus work without locks?
**Answer:**
ChronosMatch implements a **Single-Producer Single-Consumer (SPSC)** lock-free circular ring buffer mapped directly to system memory (`mmap` on Windows Named Shared Memory).
* The header contains two 64-bit atomic integer pointers: `head` (read offset) and `tail` (write offset).
* The producer writes directly to `buffer[tail % capacity]` and increments `tail`.
* The consumer reads directly from `buffer[head % capacity]` and increments `head`.
* No mutexes or OS kernel transitions are invoked on the critical path, keeping latency under **0.5 microseconds**.

### Q3: Why are C-structs 32-byte and 48-byte aligned?
**Answer:**
Modern x86_64 CPUs utilize 64-byte L1 cache lines.
* The `Order` struct is exactly **32 bytes**, meaning two orders pack cleanly into one cache line with zero false-sharing or cache boundary crossing.
* The `Execution` struct is padded to **48 bytes**, keeping struct alignment deterministic.

---

## 3. Limit Order Book (LOB) Algorithm & Data Structures

### Q4: What data structures power the Limit Order Book?
**Answer:**
* **Price Levels:** Maintained in sorted order using a binary-search price level array ($O(\log K)$ price lookup and insertion).
* **Order Queue:** Orders at the same price level form a doubly-linked list providing strict **FIFO (Price-Time Priority)** matching ($O(1)$ order enqueue, cancel, and match).
* **Order Node Pool:** Reusable pre-allocated free-list pool to eliminate dynamic `malloc`/`free` calls during the matching loop.

### Q5: What is the time complexity of core operations?
* **Best Bid / Best Ask Lookup:** $O(1)$
* **New Limit Order Insertion (existing price):** $O(1)$
* **New Limit Order Insertion (new price level):** $O(\log K)$ where $K$ is the number of active price levels.
* **Order Matching / Crossing:** $O(1)$ per matched lot.
* **Order Cancellation:** $O(1)$ via hash map pointer dereference.

---

## 4. Live Market Data & Fixed-Point Scaling

### Q6: How does ChronosMatch handle fractional Bitcoin amounts from Binance?
**Answer:**
Floating-point arithmetic in financial engines causes IEEE 754 rounding errors and slows down C-struct packing.
* Binance sends trade prices and quantities as floating-point JSON strings (e.g., `price: "67450.25"`, `qty: "0.01524000"`).
* ChronosMatch uses **fixed-point scaling**: prices are converted to integer cents (`price * 100`) or satoshis, and lot sizes are multiplied by $10^8$.
* All matching is performed using native `uint64_t` arithmetic, ensuring bitwise deterministic trade matching.

---

## 5. Quantitative Telemetry & Analytics

### Q7: How does ChronosMatch calculate VWAP and Latency metrics?
* **Volume Weighted Average Price (VWAP):**
  $$\text{VWAP} = \frac{\sum (P_i \times V_i)}{\sum V_i}$$
* **Execution Latency:** Measured at microsecond resolution:
  $$\text{Latency} = \frac{\text{Timestamp}_{\text{Outbound}} - \text{Timestamp}_{\text{Inbound}}}{1000}$$
* **Quantiles (P50, P95, P99):** Real-time sorting over rolling window of 50,000 executions to monitor tail-risk latency spikes.
