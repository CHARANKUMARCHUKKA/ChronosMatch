# ChronosMatch System Architecture Specification

## 1. Overview & Core Philosophy

**ChronosMatch** is a prototype Zero-Copy High-Frequency Trading (HFT) Engine built using **Cython** and **Python 3**. In ultra-low latency trading environments, sub-microsecond determinism is paramount. Traditional Python systems suffer from two fatal latency bottlenecks:
1. **Garbage Collection (GC) Pauses:** Python's generational garbage collector causes non-deterministic stop-the-world latency spikes.
2. **Inter-Process Serialization Overhead:** Passing data across multi-processing boundaries via sockets, pipes, or serialization libraries (JSON, Pickle) incurs memory copies and high CPU overhead.

ChronosMatch bypasses both bottlenecks by executing order matching entirely within compiled C memory structures and exchanging orders across process boundaries via **Windows Named Shared Memory** ring buffers.

---

## 2. Memory Layout & Cache Alignment

All data structures operating on the critical trading path are packed C structs with explicit byte offsets to align with CPU L1 cache lines (64 bytes).

### 2.1 Order Struct (32 Bytes)
```c
struct Order {
    uint64_t order_id;   // 8 bytes: Unique identifier (0 = STOP signal)
    uint64_t price;      // 8 bytes: Fixed-point price in cents
    uint32_t size;       // 4 bytes: Order quantity
    uint8_t  side;       // 1 byte:  0 = BUY, 1 = SELL
    uint8_t  action;     // 1 byte:  0 = NEW, 1 = CANCEL
    uint8_t  pad[2];     // 2 bytes: Explicit padding
    uint64_t timestamp;  // 8 bytes: Ingestion timestamp (nanoseconds)
}; // Total: 32 bytes (2 orders per 64-byte cache line)
```

### 2.2 Execution Struct (48 Bytes)
```c
struct Execution {
    uint64_t exec_id;    // 8 bytes: Monotonically increasing trade ID
    uint64_t order_id;   // 8 bytes: Matched order ID
    uint64_t price;      // 8 bytes: Executed match price
    uint32_t size;       // 4 bytes: Filled quantity
    uint8_t  exec_type;  // 1 byte:  0 = FILL, 1 = CANCELED
    uint8_t  pad[3];     // 3 bytes: Explicit alignment padding
    uint64_t ts_in;      // 8 bytes: Order ingress timestamp (ns)
    uint64_t ts_out;     // 8 bytes: Match completion timestamp (ns)
}; // Total: 48 bytes
```

### 2.3 RingBufferHeader Struct (24 Bytes)
```c
struct RingBufferHeader {
    uint64_t head;       // 8 bytes: Consumer read index
    uint64_t tail;       // 8 bytes: Producer write index
    uint64_t capacity;   // 8 bytes: Power-of-two buffer capacity
}; // Total: 24 bytes
```

---

## 3. Limit Order Book (LOB) Architecture

The core matching engine maintains isolated books for **Bids** (Buy) and **Asks** (Sell).

### 3.1 Sorted Price Ladder
- **Asks:** Sorted in **ascending** price order (`asks[0]` always holds the minimum ask price).
- **Bids:** Sorted in **descending** price order (`bids[0]` always holds the maximum bid price).
- **Best Bid / Best Ask Lookup:** Achieved in **$O(1)$** constant time without linear scans.
- **Level Lookup & Insertion:** Binary search achieves **$O(\log K)$** lookup, with level insertion shifting bounded to active price levels.

### 3.2 Price-Time Priority (FIFO)
Each `PriceLevel` manages a doubly-linked list of resting `OrderNode` pointers (`head` and `tail`).
- New resting orders are appended to `level.tail`.
- Aggressive incoming orders match against `level.head` first, preserving strict FIFO time priority.

### 3.3 Free-List Node Recycling Pool
To eliminate dynamic memory allocation (`malloc`/`free`) and prevent heap fragmentation on the hot path:
- The engine pre-allocates an `order_pool` of 1,000,000 `OrderNode` structs at startup.
- Depleted orders (fully filled or canceled) are returned to a single-pointer `free_list`.
- New orders pop from `free_list` in **$O(1)$** time before falling back to the bump allocator.
- This guarantees zero memory leaks and indefinite operation across billions of orders.

---

## 4. Execution & Matching Lifecycle

1. **Ingress:** Producer writes `Order` struct to inbound shared memory and increments `header.tail`.
2. **Matching Check:** Engine polls `tail > head`.
   - If `order.action == ACTION_CANCEL`: Searches book, unlinks order node, returns node to `free_list`, and emits `EXEC_CANCELED` execution record.
   - If `order.action == ACTION_NEW`:
     - Compares limit price against opposite book top (`asks[0]` or `bids[0]`).
     - If crossing, executes trades at maker resting price, decrements quantities, and emits two `EXEC_FILL` execution records (maker + taker).
     - If unexecuted size remains, inserts resting order into corresponding book.
3. **Egress:** Consumer (monitor dashboard or strategy) reads `Execution` from outbound shared memory and updates `header.head`.
